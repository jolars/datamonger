#include <R.h>
#include <R_ext/Rdynload.h>
#include <R_ext/Visibility.h>
#include <Rinternals.h>

extern SEXP dm_gzip_decompress(SEXP input);

static const R_CallMethodDef call_methods[] = {
    {"dm_gzip_decompress", (DL_FUNC) &dm_gzip_decompress, 1},
    {NULL, NULL, 0}
};

void attribute_visible R_init_datamonger(DllInfo *dll) {
    R_registerRoutines(dll, NULL, call_methods, NULL, NULL);
    R_useDynamicSymbols(dll, FALSE);
    R_forceSymbols(dll, TRUE);
}
