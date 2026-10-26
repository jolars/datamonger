#ifndef DATAMONGER_H
#define DATAMONGER_H
#include <stddef.h>
#include <stdint.h>
#ifdef _WIN32
#define DM_API __declspec(dllimport)
#else
#define DM_API
#endif
#ifdef __cplusplus
extern "C" {
#endif

/* ABI 1. All structs use the platform C layout and native byte order.
 * Borrowed input buffers must be aligned, readable, and immutable for the call.
 * Lengths count elements, not bytes, except in DmBytes. NULL is allowed only
 * for empty buffers. UTF-8 strings are length-delimited, including embedded NULs.
 * No input pointer is retained. No Rust panic unwinds into the caller.
 * Calls are independent and may run concurrently; a result may only be freed
 * once, after all users of its views have finished. */
typedef struct { const uint8_t *data; size_t len; } DmBytes;
typedef struct { const uint64_t *data; size_t len; } DmU64s;
/* Types: 1=float64, 2=int64, 3=UTF-8 string, 4=bool (one uint8_t, 0 or 1). */
typedef struct { DmBytes name; uint32_t data_type; } DmColumn;
typedef struct {
    uint32_t delimiter; /* ASCII comma or tab. */
    const DmColumn *columns;
    size_t column_count;
    const DmBytes *missing_values;
    size_t missing_count;
} DmDelimitedOptions;
typedef struct {
    uint64_t feature_count;
    uint32_t label_type;
    DmBytes target_name;
} DmLibsvmOptions;
/* Compression: 0=none, 1=gzip, 2=bzip2. Paths are UTF-8 on all platforms. */
typedef struct { DmBytes path; uint32_t compression; } DmArtifact;
typedef struct {
    DmBytes name;
    uint32_t kind; /* 1=vector, 2=sparse matrix (CSR), 3=dense matrix. */
    uint32_t data_type;
    uint64_t rows; /* Vector length for vectors. */
    uint64_t columns; /* 1 for vectors. */
    const void *values; /* double*, int64_t*, DmBytes*, or uint8_t*. */
    size_t len;
    DmBytes valid; /* One 0/1 byte per value; empty for sparse matrices. */
    DmU64s row_offsets; /* Zero-based; empty for vectors and dense matrices. */
    DmU64s column_indices; /* Zero-based; empty for nonsparse components. */
} DmComponent;
typedef struct DmResult DmResult;

DM_API uint32_t dm_abi_version(void);
DM_API DmResult *dm_decode_delimited(DmArtifact, DmDelimitedOptions);
DM_API DmResult *dm_decode_libsvm(DmArtifact, DmLibsvmOptions, DmBytes prefix);
DM_API DmResult *dm_decode_libsvm_split(DmArtifact train, DmArtifact test, DmLibsvmOptions);
/* Version 2 omits feature values that round to zero. */
DM_API DmResult *dm_decode_libsvm_v2(DmArtifact, DmLibsvmOptions, DmBytes prefix);
DM_API DmResult *dm_decode_libsvm_split_v2(DmArtifact train, DmArtifact test, DmLibsvmOptions);
/* emit_bytes=0 streams the digest without allocating a canonical byte buffer;
 * emit_bytes=1 also returns canonical bytes. Components are copied for the call. */
DM_API DmResult *dm_canonical(const DmComponent *, size_t count, uint32_t emit_bytes);
/* Status: 0=OK, 1=unsupported decoder, 2=decode (including artifact I/O),
 * 3=decoded integrity, 4=internal panic. Error messages are diagnostic text.
 * Every operation returns an owned result, including on failure. A NULL result
 * passed to an accessor is treated as an internal error or an empty view.
 * All returned buffers belong to the result and expire at dm_result_free().
 * Never write to or free an individual view. Accessors do not allocate. */
DM_API uint32_t dm_result_status(const DmResult *);
DM_API DmBytes dm_result_error(const DmResult *);
DM_API size_t dm_result_count(const DmResult *);
DM_API const DmComponent *dm_result_component(const DmResult *, size_t index);
/* A SHA-256 digest (32 raw bytes) is available on canonical results only. */
DM_API DmBytes dm_result_digest(const DmResult *);
DM_API DmBytes dm_result_bytes(const DmResult *);
DM_API void dm_result_free(DmResult *); /* NULL is a no-op. */
#ifdef __cplusplus
}
#endif
#endif
