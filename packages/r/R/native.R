.native_result <- function(result) {
  if (is.null(result$category)) return(result$value)
  if (identical(result$category, "interrupted")) {
    stop(structure(list(message = result$message, call = NULL),
                   class = c("interrupt", "condition")))
  }
  .abort_category(result$category, result$message)
}

.public_vector <- function(component) {
  values <- component$values
  if (identical(component$logical_type, "int64")) {
    return(.new_int64(values, component$valid))
  }
  values[!component$valid] <- NA
  values
}
