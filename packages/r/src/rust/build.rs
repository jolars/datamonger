fn main() {
    println!("cargo:rustc-check-cfg=cfg(local_core_v2)");
    println!("cargo:rerun-if-env-changed=DM_R_CORE_PATH");
    // The published vendor archive predates v2; local core tests exercise the new API.
    if std::env::var_os("DM_R_CORE_PATH").is_some() {
        println!("cargo:rustc-cfg=local_core_v2");
    }
}
