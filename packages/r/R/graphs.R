.graph_fields <- function(value, fields) {
  .require_exact_fields(
    value, fields, "graph recipe", "datamonger_unsupported_decoder"
  )
}

.graph_setup <- function(dataset, representation) {
  decoder <- representation$decoder
  graph <- identical(decoder, "graph-tables")
  modality <- if (graph) "graph" else "hypergraph"
  fail <- function(message) .abort_category("unsupported-decoder", message)
  if (!identical(dataset$schema_version, 8L) ||
      !identical(dataset$modality, modality) ||
      !identical(representation$decoder_version, 1L)) {
    fail("graph and HIF recipes require manifest schema 8")
  }
  roles <- if (graph) c("nodes", "edges") else "data"
  artifacts <- .representation_artifacts(dataset, representation, roles)
  compressions <- vapply(artifacts, function(a) {
    if (!.is_scalar_character(a$compression) ||
        !(a$compression %in% c("none", "gzip", "bzip2"))) {
      fail("unsupported graph artifact compression")
    }
    a$compression
  }, character(1))
  options <- representation$options
  tables <- c("nodes", "hyperedges", "incidences")
  fields <- if (graph) roles else c("node_id", "edge_id", tables)
  .graph_fields(options, c("directed", fields))
  if (!.is_scalar_logical(options$directed)) {
    fail("directed must be a boolean")
  }
  if (graph) {
    for (i in seq_along(roles)) {
      role <- roles[[i]]
      format <- artifacts[[i]]$format
      delimiter <- if (identical(format, "csv")) "," else if (identical(format, "tsv")) "\t"
      table <- .validate_delimited_options(options[[role]])
      if (!identical(table$delimiter, delimiter)) {
        fail("graph table format and delimiter disagree")
      }
      options[[role]] <- table
    }
  } else {
    id_types <- c("int64", "string")
    if (!identical(artifacts[[1L]]$format, "hif") ||
        !all(vapply(options[c("node_id", "edge_id")], function(id) {
          .is_scalar_character(id) && id %in% id_types
        }, logical(1)))) {
      fail("invalid HIF artifact format or ID type")
    }
    reserved <- list(nodes = "id", hyperedges = "id", incidences = c("node", "edge", "direction"))
    for (role in tables) {
      table <- options[[role]]
      .graph_fields(table, c("weight", "attributes"))
      if (!.is_scalar_logical(table$weight)) fail("invalid HIF weight option")
      attributes <- .require_array(table$attributes, "HIF attributes", "datamonger_unsupported_decoder")
      seen <- c(reserved[[role]], if (table$weight) "weight")
      for (attribute in attributes) {
        .graph_fields(attribute, c("name", "type"))
        if (!.is_scalar_character(attribute$name) || !nzchar(attribute$name) ||
            attribute$name %in% seen || !.is_scalar_character(attribute$type) ||
            !(attribute$type %in% c("int64", "string", "float64", "bool"))) {
          fail("invalid or duplicate HIF attribute")
        }
        seen <- c(seen, attribute$name)
      }
    }
  }
  list(representation = representation, decoder = decoder, artifacts = artifacts,
       options = options, compressions = compressions)
}

.decode_graph <- function(setup, paths, hash) {
  decoded <- .native_result(dm_decode(
    setup$decoder, paths, setup$compressions, setup$options, hash
  ))
  graph <- identical(setup$decoder, "graph-tables")
  roles <- if (graph) c("nodes", "edges") else c("nodes", "hyperedges", "incidences")
  components <- decoded$components
  names <- vapply(components, `[[`, character(1), "name")
  data <- list(directed = setup$options$directed)
  for (role in roles) {
    prefix <- paste0(role, "/")
    selected <- startsWith(names, prefix)
    columns <- lapply(components[selected], .public_vector)
    names(columns) <- substring(names[selected], nchar(prefix) + 1L)
    data[[role]] <- structure(columns, row.names = seq_along(columns[[1L]]),
                              class = "data.frame")
  }
  class(data) <- c(if (graph) "datamonger_graph_dataset" else "datamonger_hypergraph_dataset", "list")
  decoded$data <- data
  decoded
}
