//! Private Python conversions around the language-independent decoder.

use std::fs::File;
use std::path::PathBuf;

use datamonger_core as core;
use numpy::{IntoPyArray, PyReadonlyArray1};
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyTuple};

pyo3::import_exception!(datamonger._errors, DecodeError);
pyo3::import_exception!(datamonger._errors, UnsupportedDecoderError);

fn decode_error(error: core::Error) -> PyErr {
    match error.kind {
        core::ErrorKind::UnsupportedDecoder => UnsupportedDecoderError::new_err(error.to_string()),
        _ => DecodeError::new_err(error.to_string()),
    }
}

fn data_type(value: &str) -> PyResult<core::DataType> {
    match value {
        "float64" => Ok(core::DataType::Float64),
        "int64" => Ok(core::DataType::Int64),
        "string" => Ok(core::DataType::String),
        "bool" => Ok(core::DataType::Bool),
        _ => Err(PyValueError::new_err("unsupported logical type")),
    }
}

fn compression(value: &str) -> PyResult<core::Compression> {
    match value {
        "none" => Ok(core::Compression::None),
        "gzip" => Ok(core::Compression::Gzip),
        "bzip2" => Ok(core::Compression::Bzip2),
        _ => Err(UnsupportedDecoderError::new_err(format!(
            "unsupported compression: {value:?}"
        ))),
    }
}

fn reader(path: PathBuf, coding: core::Compression) -> core::Result<Box<dyn std::io::BufRead>> {
    Ok(core::artifact_reader_with_options(
        File::open(path)?,
        coding,
        core::ArtifactReaderOptions {
            gzip_zero_padding: true,
            bzip2_trailing_data: true,
        },
    ))
}

fn artifact_error(error: core::Error, compression: &str) -> core::Error {
    if error.kind == core::ErrorKind::Io {
        let operation = if compression == "none" {
            "read".to_owned()
        } else {
            format!("decompress {compression}")
        };
        core::Error::new(error.kind, format!("cannot {operation} artifact: {error}"))
    } else {
        error
    }
}

// Store the original Python exception so cancellation preserves custom signal
// handlers as well as KeyboardInterrupt across the core's portable error type.
fn run<T: Send>(
    py: Python<'_>,
    operation: impl FnOnce(&mut dyn core::Control) -> core::Result<T> + Send,
) -> PyResult<T> {
    let mut interrupted = None;
    let result = py.detach(|| {
        operation(&mut || {
            Python::attach(|py| {
                py.check_signals().map_err(|error| {
                    interrupted = Some(error);
                    core::Error::new(core::ErrorKind::Interrupted, "interrupted")
                })
            })
        })
    });
    if let Some(error) = interrupted {
        return Err(error);
    }
    result.map_err(decode_error)
}

fn to_python(py: Python<'_>, components: Vec<core::Component>) -> PyResult<Vec<Py<PyAny>>> {
    let models = py.import("datamonger._models")?;
    components
        .into_iter()
        .map(|component| {
            let logical_type = match component.values.data_type() {
                core::DataType::Float64 => "float64",
                core::DataType::Int64 => "int64",
                core::DataType::String => "string",
                core::DataType::Bool => "bool",
            };
            let values = match component.values {
                core::Values::Float64(v) => v.into_pyarray(py).into_any(),
                core::Values::Int64(v) => v.into_pyarray(py).into_any(),
                core::Values::Bool(v) => v.into_pyarray(py).into_any(),
                core::Values::String(v) => PyTuple::new(py, v)?.into_any(),
            };
            let result = match component.shape {
                core::Shape::Vector => models.getattr("LogicalComponent")?.call1((
                    component.name,
                    logical_type,
                    values,
                    component.valid.into_pyarray(py),
                ))?,
                core::Shape::Sparse {
                    rows,
                    columns,
                    row_offsets,
                    column_indices,
                } => {
                    let signed = |values: Vec<u64>| -> PyResult<Vec<i64>> {
                        values
                            .into_iter()
                            .map(|v| {
                                i64::try_from(v)
                                    .map_err(|_| DecodeError::new_err("index exceeds int64"))
                            })
                            .collect()
                    };
                    models.getattr("LogicalSparseMatrix")?.call1((
                        component.name,
                        rows,
                        columns,
                        signed(row_offsets)?.into_pyarray(py),
                        signed(column_indices)?.into_pyarray(py),
                        values,
                    ))?
                }
                core::Shape::Dense { .. } => unreachable!("decoders produce vectors or CSR"),
            };
            Ok(result.unbind())
        })
        .collect()
}

#[pyfunction]
fn decode_delimited(
    py: Python<'_>,
    path: PathBuf,
    columns: Vec<(String, String)>,
    missing_values: Vec<String>,
    delimiter: &str,
    compression: &str,
) -> PyResult<Vec<Py<PyAny>>> {
    let coding = self::compression(compression)?;
    let options = core::DelimitedOptions {
        columns: columns
            .into_iter()
            .map(|(name, kind)| {
                Ok(core::Column {
                    name,
                    data_type: data_type(&kind)?,
                })
            })
            .collect::<PyResult<_>>()?,
        delimiter: match delimiter {
            "," => b',',
            "\t" => b'\t',
            _ => return Err(UnsupportedDecoderError::new_err("unsupported delimiter")),
        },
        missing_values,
    };
    let components = run(py, |control| {
        reader(path, coding)
            .and_then(|reader| {
                core::decode_delimited_with_control(reader, &options, &mut || control.checkpoint())
            })
            .map_err(|error| artifact_error(error, compression))
    })?;
    to_python(py, components)
}

#[pyfunction]
fn decode_libsvm(
    py: Python<'_>,
    path: PathBuf,
    feature_count: u64,
    label_type: &str,
    target_name: String,
    compression: &str,
) -> PyResult<Vec<Py<PyAny>>> {
    let coding = self::compression(compression)?;
    let options = core::LibsvmOptions {
        feature_count,
        label_type: match label_type {
            "int64" => core::LabelType::Int64,
            "float64" => core::LabelType::Float64,
            _ => return Err(UnsupportedDecoderError::new_err("unsupported label_type")),
        },
        target_name,
    };
    let components = run(py, |control| {
        reader(path, coding)
            .and_then(|reader| {
                core::decode_libsvm_with_control(reader, &options, &mut || control.checkpoint())
            })
            .map_err(|error| artifact_error(error, compression))
    })?;
    to_python(py, components)
}

fn array<T: numpy::Element + Copy>(value: &Bound<'_, PyAny>) -> PyResult<Vec<T>> {
    // Iterate in logical order so sliced and noncontiguous arrays stay valid.
    Ok(value
        .extract::<PyReadonlyArray1<'_, T>>()?
        .as_array()
        .iter()
        .copied()
        .collect())
}

fn from_python(components: &Bound<'_, PyAny>) -> PyResult<Vec<core::Component>> {
    let models = components.py().import("datamonger._models")?;
    let sparse = models.getattr("LogicalSparseMatrix")?;
    let dense = models.getattr("LogicalDenseMatrix")?;
    components
        .try_iter()?
        .map(|component| {
            let component = component?;
            let name = component
                .getattr("name")?
                .extract::<String>()
                .map_err(|_| PyValueError::new_err("component name is not valid UTF-8"))?;
            if name.is_empty() {
                return Err(PyValueError::new_err("component names must not be empty"));
            }
            let raw_values = component.getattr("values")?;
            let is_sparse = component.is_instance(&sparse)?;
            let valid: Vec<bool> = if is_sparse {
                Vec::new()
            } else {
                array(&component.getattr("valid")?)?
            };
            let kind = component.getattr("logical_type")?.extract::<String>()?;
            let values = match data_type(&kind)? {
                core::DataType::Float64 => core::Values::Float64(array(&raw_values)?),
                core::DataType::Int64 => core::Values::Int64(array(&raw_values)?),
                core::DataType::Bool => core::Values::Bool(array(&raw_values)?),
                core::DataType::String => core::Values::String(
                    raw_values
                        .try_iter()?
                        .enumerate()
                        .map(|(index, value)| {
                            if !valid.get(index).copied().unwrap_or(false) {
                                Ok(String::new())
                            } else {
                                value?.extract::<String>().map_err(|_| {
                                    PyValueError::new_err("logical string is not valid UTF-8")
                                })
                            }
                        })
                        .collect::<PyResult<_>>()?,
                ),
            };
            let dimension = |field| -> PyResult<u64> {
                let value = component.getattr(field)?;
                if value.is_instance_of::<pyo3::types::PyBool>() {
                    return Err(PyValueError::new_err("dimension must be an integer"));
                }
                value
                    .extract()
                    .map_err(|_| PyValueError::new_err("dimension exceeds uint64 framing"))
            };
            let shape = if is_sparse {
                let unsigned = |field| -> PyResult<Vec<u64>> {
                    array::<i64>(&component.getattr(field)?)?
                        .into_iter()
                        .map(|v| {
                            u64::try_from(v).map_err(|_| {
                                PyValueError::new_err("negative sparse index or offset")
                            })
                        })
                        .collect()
                };
                core::Shape::Sparse {
                    rows: dimension("rows")?,
                    columns: dimension("columns")?,
                    row_offsets: unsigned("row_offsets")?,
                    column_indices: unsigned("column_indices")?,
                }
            } else if component.is_instance(&dense)? {
                core::Shape::Dense {
                    rows: dimension("rows")?,
                    columns: dimension("columns")?,
                }
            } else {
                core::Shape::Vector
            };
            Ok(core::Component {
                name,
                shape,
                values,
                valid,
            })
        })
        .collect()
}

#[pyfunction]
fn canonical_bytes<'py>(
    py: Python<'py>,
    components: &Bound<'_, PyAny>,
) -> PyResult<Bound<'py, PyBytes>> {
    let components = from_python(components)?;
    let mut bytes = Vec::new();
    // Canonical component errors have always been ValueError in the private
    // encoder; public fetch integrity failures are classified by Python.
    run(py, |control| {
        core::write_canonical_with_control(&components, &mut bytes, &mut || control.checkpoint())
    })
    .map_err(canonical_error)?;
    Ok(PyBytes::new(py, &bytes))
}

fn canonical_error(error: PyErr) -> PyErr {
    Python::attach(|py| {
        if error.is_instance_of::<DecodeError>(py) {
            PyValueError::new_err(error.to_string())
        } else {
            error
        }
    })
}

#[pyfunction]
fn canonical_sha256(py: Python<'_>, components: &Bound<'_, PyAny>) -> PyResult<String> {
    let components = from_python(components)?;
    let digest = run(py, |control| {
        core::canonical_sha256_with_control(&components, &mut || control.checkpoint())
    })
    .map_err(canonical_error)?;
    Ok(digest.iter().map(|b| format!("{b:02x}")).collect())
}

#[pymodule]
fn _native(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(decode_delimited, module)?)?;
    module.add_function(wrap_pyfunction!(decode_libsvm, module)?)?;
    module.add_function(wrap_pyfunction!(canonical_bytes, module)?)?;
    module.add_function(wrap_pyfunction!(canonical_sha256, module)?)?;
    Ok(())
}
