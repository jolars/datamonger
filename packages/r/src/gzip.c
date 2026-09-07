#include <R.h>
#include <Rinternals.h>

#include <limits.h>
#include <stdint.h>
#include <string.h>
#include <zlib.h>

enum inflate_result {
    DM_INFLATE_OK = 0,
    DM_INFLATE_INVALID,
    DM_INFLATE_TRAILING,
    DM_INFLATE_TOO_LARGE
};

static enum inflate_result inflate_once(
    const Bytef *input,
    R_xlen_t input_size,
    Bytef *output,
    R_xlen_t output_capacity,
    R_xlen_t *output_size
) {
    z_stream stream;
    unsigned char scratch[65536];
    R_xlen_t fed = 0;
    R_xlen_t produced_total = 0;
    int status;

    memset(&stream, 0, sizeof(stream));
    if (inflateInit2(&stream, 16 + MAX_WBITS) != Z_OK) {
        return DM_INFLATE_INVALID;
    }

    for (;;) {
        uInt output_chunk;
        uInt before_in;

        if (stream.avail_in == 0 && fed < input_size) {
            R_xlen_t remaining = input_size - fed;
            uInt input_chunk = remaining > UINT_MAX ? UINT_MAX : (uInt) remaining;
            stream.next_in = (Bytef *) input + fed;
            stream.avail_in = input_chunk;
            fed += input_chunk;
        }

        if (output == NULL) {
            stream.next_out = scratch;
            output_chunk = sizeof(scratch);
        } else if (produced_total < output_capacity) {
            R_xlen_t remaining = output_capacity - produced_total;
            output_chunk = remaining > UINT_MAX ? UINT_MAX : (uInt) remaining;
            stream.next_out = output + produced_total;
        } else {
            stream.next_out = scratch;
            output_chunk = 1;
        }
        stream.avail_out = output_chunk;
        before_in = stream.avail_in;
        status = inflate(&stream, Z_NO_FLUSH);

        if ((R_xlen_t) (output_chunk - stream.avail_out) >
            R_XLEN_T_MAX - produced_total) {
            inflateEnd(&stream);
            return DM_INFLATE_TOO_LARGE;
        }
        produced_total += (R_xlen_t) (output_chunk - stream.avail_out);
        if (output != NULL && produced_total > output_capacity) {
            inflateEnd(&stream);
            return DM_INFLATE_TOO_LARGE;
        }

        if (status == Z_STREAM_END) {
            enum inflate_result result =
                stream.avail_in == 0 && fed == input_size
                    ? DM_INFLATE_OK
                    : DM_INFLATE_TRAILING;
            inflateEnd(&stream);
            *output_size = produced_total;
            return result;
        }
        if (status != Z_OK ||
            (stream.avail_in == before_in && stream.avail_out == output_chunk)) {
            inflateEnd(&stream);
            return DM_INFLATE_INVALID;
        }
    }
}

SEXP dm_gzip_decompress(SEXP input) {
    enum inflate_result result;
    R_xlen_t output_size = 0;
    R_xlen_t second_size = 0;
    SEXP output;

    if (TYPEOF(input) != RAWSXP) {
        Rf_error("gzip input must be a raw vector");
    }

    result = inflate_once(RAW(input), XLENGTH(input), NULL, 0, &output_size);
    if (result == DM_INFLATE_TRAILING) {
        Rf_error("gzip stream contains trailing bytes or additional members");
    }
    if (result == DM_INFLATE_TOO_LARGE) {
        Rf_error("gzip output is too large for an R raw vector");
    }
    if (result != DM_INFLATE_OK) {
        Rf_error("gzip stream is malformed or truncated");
    }

    output = PROTECT(Rf_allocVector(RAWSXP, output_size));
    result = inflate_once(
        RAW(input),
        XLENGTH(input),
        RAW(output),
        output_size,
        &second_size
    );
    if (result != DM_INFLATE_OK || second_size != output_size) {
        UNPROTECT(1);
        Rf_error("gzip stream changed while it was being decoded");
    }
    UNPROTECT(1);
    return output;
}
