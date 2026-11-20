use std::collections::HashSet;

use crate::{Component, Error, ErrorKind, Result, Shape, Values};

#[derive(Clone, Copy, Debug, Eq, Hash, PartialEq)]
enum Id<'a> {
    Integer(i64),
    Text(&'a str),
}

fn invalid(message: &str) -> Error {
    Error::new(ErrorKind::Decode, message)
}

fn column<'a>(table: &'a [Component], name: &str) -> Result<&'a Component> {
    table
        .iter()
        .find(|column| column.name == name)
        .ok_or_else(|| invalid(&format!("missing topology column {name:?}")))
}

fn ids(column: &Component) -> Result<Vec<Id<'_>>> {
    if column.valid.contains(&false) {
        return Err(invalid("topology IDs cannot be null"));
    }
    match &column.values {
        Values::Int64(values) => Ok(values.iter().copied().map(Id::Integer).collect()),
        Values::String(values) => Ok(values.iter().map(|id| Id::Text(id)).collect()),
        _ => Err(invalid("topology IDs must be int64 or string")),
    }
}

fn keys(column: &Component) -> Result<HashSet<Id<'_>>> {
    let ids = ids(column)?;
    let count = ids.len();
    let keys: HashSet<_> = ids.into_iter().collect();
    if keys.len() != count {
        return Err(invalid("duplicate entity ID"));
    }
    Ok(keys)
}

fn references<'a>(
    column: &'a Component,
    key: &Component,
    known: &HashSet<Id<'_>>,
) -> Result<Vec<Id<'a>>> {
    if column.values.data_type() != key.values.data_type() {
        return Err(invalid("reference and entity ID types differ"));
    }
    let values = ids(column)?;
    if values.iter().any(|id| !known.contains(id)) {
        return Err(invalid("unknown entity ID in topology reference"));
    }
    Ok(values)
}

fn validate_table(table: &[Component]) -> Result<()> {
    let rows = table
        .first()
        .ok_or_else(|| invalid("topology table has no columns"))?
        .values
        .len();
    let mut names = HashSet::new();
    for column in table {
        if column.shape != Shape::Vector
            || column.values.len() != rows
            || column.valid.len() != rows
            || column.name.is_empty()
            || !names.insert(&column.name)
        {
            return Err(invalid("invalid topology table columns"));
        }
    }
    Ok(())
}

fn assemble(
    directed: bool,
    tables: impl IntoIterator<Item = (&'static str, Vec<Component>)>,
) -> Vec<Component> {
    let mut components = vec![Component {
        name: "directed".into(),
        shape: Shape::Vector,
        values: Values::Bool(vec![directed]),
        valid: vec![true],
    }];
    for (name, table) in tables {
        components.extend(table.into_iter().map(|mut column| {
            column.name = format!("{name}/{}", column.name);
            column
        }));
    }
    components
}

/// Validate graph tables and return their canonical components in table order.
pub fn assemble_graph(
    directed: bool,
    nodes: Vec<Component>,
    edges: Vec<Component>,
) -> Result<Vec<Component>> {
    validate_table(&nodes)?;
    validate_table(&edges)?;
    let node_key = column(&nodes, "id")?;
    let node_ids = keys(node_key)?;
    references(column(&edges, "source")?, node_key, &node_ids)?;
    references(column(&edges, "target")?, node_key, &node_ids)?;
    if let Some(edge_key) = edges.iter().find(|column| column.name == "id") {
        keys(edge_key)?;
    }
    Ok(assemble(directed, [("nodes", nodes), ("edges", edges)]))
}

/// Validate hypergraph tables and return their canonical components in table order.
pub fn assemble_hypergraph(
    directed: bool,
    nodes: Vec<Component>,
    hyperedges: Vec<Component>,
    incidences: Vec<Component>,
) -> Result<Vec<Component>> {
    validate_table(&nodes)?;
    validate_table(&hyperedges)?;
    validate_table(&incidences)?;
    let node_key = column(&nodes, "id")?;
    let edge_key = column(&hyperedges, "id")?;
    let members = references(column(&incidences, "node")?, node_key, &keys(node_key)?)?;
    let edges = references(column(&incidences, "edge")?, edge_key, &keys(edge_key)?)?;
    let directions = if directed {
        let direction = column(&incidences, "direction")?;
        match &direction.values {
            Values::String(values)
                if !direction.valid.contains(&false)
                    && values
                        .iter()
                        .all(|value| matches!(value.as_str(), "head" | "tail")) =>
            {
                Some(values.as_slice())
            }
            _ => return Err(invalid("directed incidences require head or tail")),
        }
    } else {
        if incidences.iter().any(|column| column.name == "direction") {
            return Err(invalid("undirected incidences cannot specify direction"));
        }
        None
    };
    let mut seen = HashSet::new();
    for (row, (node, edge)) in members.into_iter().zip(edges).enumerate() {
        let role = directions.map(|values| values[row].as_str());
        if !seen.insert((node, edge, role)) {
            return Err(invalid("duplicate hyperedge membership"));
        }
    }
    Ok(assemble(
        directed,
        [
            ("nodes", nodes),
            ("hyperedges", hyperedges),
            ("incidences", incidences),
        ],
    ))
}

/// The scalar columns declared for a HIF table.
#[derive(Clone, Debug, Default)]
pub struct HifColumns {
    /// Attributes in canonical column order.
    pub attributes: Vec<(String, crate::DataType)>,
    /// Include the HIF record's top-level weight.
    pub weight: bool,
}

/// The types and attributes selected by a version 1 HIF recipe.
#[derive(Clone, Debug)]
pub struct HifOptions {
    /// Whether the document must contain a directed hypergraph.
    pub directed: bool,
    /// Type of all node IDs.
    pub node_id: crate::DataType,
    /// Type of all hyperedge IDs.
    pub edge_id: crate::DataType,
    /// Node columns.
    pub nodes: HifColumns,
    /// Hyperedge columns.
    pub hyperedges: HifColumns,
    /// Incidence columns.
    pub incidences: HifColumns,
}

use crate::DataType;
use serde_json::{Map, Value};

fn vector(name: &str, data_type: DataType) -> Component {
    Component {
        name: name.into(),
        shape: Shape::Vector,
        values: Values::empty(data_type),
        valid: Vec::new(),
    }
}

fn push(column: &mut Component, value: &Value, required: bool) -> Result<()> {
    let missing = value.is_null() && !required;
    match &mut column.values {
        Values::Int64(values) => values.push(if missing {
            0
        } else {
            value
                .as_i64()
                .ok_or_else(|| invalid("expected an int64 JSON value"))?
        }),
        Values::String(values) => values.push(if missing {
            String::new()
        } else {
            value
                .as_str()
                .ok_or_else(|| invalid("expected a JSON string"))?
                .to_owned()
        }),
        Values::Bool(values) => values.push(if missing {
            false
        } else {
            value
                .as_bool()
                .ok_or_else(|| invalid("expected a JSON boolean"))?
        }),
        Values::Float64(values) => values.push(if missing {
            0.0
        } else {
            value
                .as_f64()
                .ok_or_else(|| invalid("expected a binary64 JSON number"))?
        }),
    }
    column.valid.push(!missing);
    Ok(())
}

fn validate_fields(record: &Map<String, Value>, allowed: &[&str]) -> Result<()> {
    if record.keys().any(|key| !allowed.contains(&key.as_str())) {
        return Err(invalid("unknown HIF field"));
    }
    Ok(())
}

fn append_hif_columns(columns: &mut Vec<Component>, options: &HifColumns) {
    if options.weight {
        columns.push(vector("weight", DataType::Float64));
    }
    columns.extend(
        options
            .attributes
            .iter()
            .map(|(name, kind)| vector(name, *kind)),
    );
}

fn append_attributes(
    columns: &mut [Component],
    record: &Map<String, Value>,
    options: &HifColumns,
) -> Result<()> {
    let attrs = record
        .get("attrs")
        .map(|value| {
            value
                .as_object()
                .ok_or_else(|| invalid("HIF attrs must be an object"))
        })
        .transpose()?;
    if attrs.is_some_and(|attrs| {
        attrs
            .keys()
            .any(|key| !options.attributes.iter().any(|(name, _)| name == key))
    }) {
        return Err(invalid("undeclared HIF attribute"));
    }
    let columns = if options.weight {
        push(
            &mut columns[0],
            record.get("weight").unwrap_or(&Value::Null),
            false,
        )?;
        &mut columns[1..]
    } else {
        if record.contains_key("weight") {
            return Err(invalid("undeclared HIF weight"));
        }
        columns
    };
    for column in columns {
        let value = attrs
            .and_then(|attrs| attrs.get(&column.name))
            .unwrap_or(&Value::Null);
        push(column, value, false)?;
    }
    Ok(())
}

fn json_id(value: &Value) -> Result<Id<'_>> {
    if let Some(value) = value.as_i64() {
        Ok(Id::Integer(value))
    } else {
        value
            .as_str()
            .map(Id::Text)
            .ok_or_else(|| invalid("invalid HIF ID"))
    }
}

fn hif_rows<'a>(
    document: &'a Map<String, Value>,
    name: &str,
    required: bool,
) -> Result<&'a [Value]> {
    match document.get(name) {
        Some(value) => value
            .as_array()
            .map(Vec::as_slice)
            .ok_or_else(|| invalid("expected HIF array")),
        None if !required => Ok(&[]),
        None => Err(invalid("missing HIF array")),
    }
}

fn hif_entities(
    declared: &[Value],
    incidences: &[Value],
    key: &str,
    kind: DataType,
    options: &HifColumns,
) -> Result<Vec<Component>> {
    let mut columns = vec![vector("id", kind)];
    append_hif_columns(&mut columns, options);
    let mut seen = HashSet::new();
    for row in declared {
        let record = row
            .as_object()
            .ok_or_else(|| invalid("expected HIF entity object"))?;
        validate_fields(record, &[key, "attrs", "weight"])?;
        if !seen.insert(json_id(&row[key])?) {
            return Err(invalid("duplicate HIF entity ID"));
        }
        push(&mut columns[0], &row[key], true)?;
        append_attributes(&mut columns[1..], record, options)?;
    }
    for row in incidences {
        if seen.insert(json_id(&row[key])?) {
            push(&mut columns[0], &row[key], true)?;
            for column in &mut columns[1..] {
                push(column, &Value::Null, false)?;
            }
        }
    }
    Ok(columns)
}

/// Decode a HIF hypergraph into canonical components.
pub fn decode_hif(reader: impl std::io::Read, options: &HifOptions) -> Result<Vec<Component>> {
    let value: Value = serde_json::from_reader(reader)
        .map_err(|error| Error::new(ErrorKind::Decode, error.to_string()))?;
    let doc = value
        .as_object()
        .ok_or_else(|| invalid("expected HIF object"))?;
    validate_fields(
        doc,
        &["nodes", "edges", "incidences", "network-type", "metadata"],
    )?;
    if doc.get("metadata").is_some_and(|value| !value.is_object()) {
        return Err(invalid("expected HIF metadata object"));
    }
    let expected = if options.directed {
        "directed"
    } else {
        "undirected"
    };
    match doc.get("network-type") {
        None if !options.directed => (),
        Some(kind) if kind.as_str() == Some(expected) => (),
        _ => return Err(invalid("HIF network type does not match recipe")),
    }
    let incidence_rows = hif_rows(doc, "incidences", true)?;
    let nodes = hif_entities(
        hif_rows(doc, "nodes", false)?,
        incidence_rows,
        "node",
        options.node_id,
        &options.nodes,
    )?;
    let edges = hif_entities(
        hif_rows(doc, "edges", false)?,
        incidence_rows,
        "edge",
        options.edge_id,
        &options.hyperedges,
    )?;
    let mut incidences = vec![
        vector("node", options.node_id),
        vector("edge", options.edge_id),
    ];
    if options.directed {
        incidences.push(vector("direction", DataType::String));
    }
    let structural = incidences.len();
    append_hif_columns(&mut incidences, &options.incidences);
    for row in incidence_rows {
        let record = row
            .as_object()
            .ok_or_else(|| invalid("expected HIF incidence object"))?;
        validate_fields(record, &["node", "edge", "direction", "attrs", "weight"])?;
        if !options.directed && record.contains_key("direction") {
            return Err(invalid("undirected incidences cannot specify direction"));
        }
        for column in &mut incidences[..structural] {
            push(column, &row[&column.name], true)?;
        }
        append_attributes(&mut incidences[structural..], record, &options.incidences)?;
    }
    assemble_hypergraph(options.directed, nodes, edges, incidences)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn options(directed: bool) -> HifOptions {
        HifOptions {
            directed,
            node_id: DataType::String,
            edge_id: DataType::Int64,
            nodes: HifColumns {
                attributes: vec![("label".into(), DataType::String)],
                weight: false,
            },
            hyperedges: HifColumns::default(),
            incidences: HifColumns::default(),
        }
    }

    #[test]
    fn hif_preserves_explicit_and_inferred_entities_and_direction() {
        let json = br#"{
            "network-type":"directed",
            "nodes":[{"node":"isolate","attrs":{"label":"Isolated"}}],
            "edges":[{"edge":42}],
            "incidences":[
                {"node":"a","edge":7,"direction":"tail"},
                {"node":"a","edge":7,"direction":"head"}
            ]
        }"#;
        let decoded = decode_hif(&json[..], &options(true)).unwrap();
        assert_eq!(decoded[0].values, Values::Bool(vec![true]));
        assert_eq!(decoded[1].name, "nodes/id");
        assert_eq!(
            decoded[1].values,
            Values::String(vec!["isolate".into(), "a".into()])
        );
        assert_eq!(decoded[2].valid, vec![true, false]);
        assert_eq!(decoded[3].name, "hyperedges/id");
        assert_eq!(decoded[3].values, Values::Int64(vec![42, 7]));
        assert_eq!(
            decoded[6].values,
            Values::String(vec!["tail".into(), "head".into()])
        );
    }

    #[test]
    fn rejects_duplicate_membership() {
        let json = br#"{"incidences":[{"node":"a","edge":7},{"node":"a","edge":7}]}"#;
        let error = decode_hif(&json[..], &options(false)).unwrap_err();
        assert_eq!(error.kind, ErrorKind::Decode);
        assert_eq!(error.to_string(), "duplicate hyperedge membership");
    }

    #[test]
    fn graph_keeps_parallel_loops_and_rejects_dangling_endpoints() {
        fn ids(name: &str, values: &[i64]) -> Component {
            Component {
                name: name.into(),
                shape: Shape::Vector,
                values: Values::Int64(values.to_vec()),
                valid: vec![true; values.len()],
            }
        }

        let nodes = vec![ids("id", &[7, 9])];
        let edges = vec![ids("source", &[7, 7]), ids("target", &[7, 7])];
        let result = assemble_graph(false, nodes.clone(), edges).unwrap();
        assert_eq!(result[3].values, Values::Int64(vec![7, 7]));
        let edges = vec![ids("source", &[7]), ids("target", &[8])];
        assert_eq!(
            assemble_graph(false, nodes, edges).unwrap_err().kind,
            ErrorKind::Decode
        );
    }
}
