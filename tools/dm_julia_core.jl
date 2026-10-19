# Build the checkout's native library and install it as a Julia artifact.
using Pkg.Artifacts
using Libdl

root = dirname(@__DIR__)
manifest = joinpath(root, "crates", "datamonger-ffi", "Cargo.toml")
cargo = get(ENV, "DM_CORE_CARGO", "cargo")
command = `$cargo build --locked --release --manifest-path $manifest`
if haskey(ENV, "DM_CORE_RUSTC")
    command = addenv(command, "RUSTC" => ENV["DM_CORE_RUSTC"])
end
run(command)
library = joinpath(dirname(manifest), "target", "release",
                   (Sys.iswindows() ? "" : "lib") * "datamonger_ffi.$(Libdl.dlext)")
hash = create_artifact() do directory
    mkpath(joinpath(directory, "lib"))
    cp(library, joinpath(directory, "lib", "datamonger_ffi.$(Libdl.dlext)"))
end
bind_artifact!(joinpath(root, "packages", "julia", "deps", "Artifacts.toml"),
               "datamonger_core", hash; platform=Base.BinaryPlatforms.HostPlatform(), force=true)
println("Installed local native artifact: $hash")
