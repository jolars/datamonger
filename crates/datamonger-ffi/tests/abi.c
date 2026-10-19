#include "datamonger.h"
#include <assert.h>
#include <string.h>

static DmBytes bytes(const char *text) {
    DmBytes value = {(const uint8_t *)text, strlen(text)};
    return value;
}

int main(int argc, char **argv) {
    assert(argc == 2);
    assert(dm_abi_version() == 1);
    DmArtifact artifact = {bytes(argv[1]), 0};
    DmLibsvmOptions options = {4, 2, bytes("response")};
    DmResult *decoded = dm_decode_libsvm(artifact, options, bytes(""));
    assert(dm_result_status(decoded) == 0);
    assert(dm_result_count(decoded) == 2);
    DmComponent components[2];
    components[0] = *dm_result_component(decoded, 0);
    components[1] = *dm_result_component(decoded, 1);
    assert(components[0].kind == 2 && components[0].data_type == 1);
    assert(components[0].row_offsets.len == components[0].rows + 1);
    assert(components[1].kind == 1 && components[1].data_type == 2);
    assert(dm_result_component(decoded, 2) == NULL);
    DmResult *canonical = dm_canonical(components, 2, 1);
    assert(dm_result_status(canonical) == 0);
    assert(dm_result_digest(canonical).len == 32);
    assert(dm_result_bytes(canonical).len > 10);
    assert(memcmp(dm_result_bytes(canonical).data, "DMCF", 4) == 0);
    dm_result_free(decoded);
    assert(memcmp(dm_result_bytes(canonical).data, "DMCF", 4) == 0);
    dm_result_free(canonical);
    DmResult *invalid = dm_canonical(NULL, 1, 0);
    assert(dm_result_status(invalid) == 3);
    assert(dm_result_error(invalid).len > 0);
    dm_result_free(invalid);
    dm_result_free(NULL);
    return 0;
}
