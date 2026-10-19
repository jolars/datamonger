/// The four revision 1 logical element types.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum DataType {
    /// IEEE 754 binary64.
    Float64,
    /// Exact signed 64-bit integers.
    Int64,
    /// UTF-8 strings without normalization.
    String,
    /// Boolean values.
    Bool,
}

/// Contiguous logical values. Validity is stored separately on the component.
#[derive(Clone, Debug, PartialEq)]
pub enum Values {
    /// Floating-point values.
    Float64(Vec<f64>),
    /// Signed integers.
    Int64(Vec<i64>),
    /// Strings, including valid empty strings.
    String(Vec<String>),
    /// Booleans.
    Bool(Vec<bool>),
}

impl Values {
    /// Logical element count.
    pub fn len(&self) -> usize {
        match self {
            Self::Float64(v) => v.len(),
            Self::Int64(v) => v.len(),
            Self::String(v) => v.len(),
            Self::Bool(v) => v.len(),
        }
    }
    /// Whether the value buffer is empty.
    pub fn is_empty(&self) -> bool {
        self.len() == 0
    }
    /// The logical type of this value buffer.
    pub fn data_type(&self) -> DataType {
        match self {
            Self::Float64(_) => DataType::Float64,
            Self::Int64(_) => DataType::Int64,
            Self::String(_) => DataType::String,
            Self::Bool(_) => DataType::Bool,
        }
    }
    pub(crate) fn empty(data_type: DataType) -> Self {
        match data_type {
            DataType::Float64 => Self::Float64(Vec::new()),
            DataType::Int64 => Self::Int64(Vec::new()),
            DataType::String => Self::String(Vec::new()),
            DataType::Bool => Self::Bool(Vec::new()),
        }
    }
}

/// Logical dimensions and sparse structure, independent of host matrix layout.
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum Shape {
    /// A vector; its length is the value count.
    Vector,
    /// Dense row-major logical values.
    Dense {
        /// Row count.
        rows: u64,
        /// Column count.
        columns: u64,
    },
    /// Zero-based compressed sparse rows, with increasing indices in each row.
    Sparse {
        /// Row count.
        rows: u64,
        /// Column count.
        columns: u64,
        /// Exactly `rows + 1` offsets into the value buffer.
        row_offsets: Vec<u64>,
        /// One column index per stored value.
        column_indices: Vec<u64>,
    },
}

/// One named logical component in decoder-defined order.
#[derive(Clone, Debug, PartialEq)]
pub struct Component {
    /// A nonempty UTF-8 name, unique within a dataset.
    pub name: String,
    /// Dimensions and optional sparse structure.
    pub shape: Shape,
    /// Typed logical values.
    pub values: Values,
    /// One validity bit per dense or vector value; empty for sparse matrices.
    pub valid: Vec<bool>,
}
