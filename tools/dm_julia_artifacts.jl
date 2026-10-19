# Package native libraries and assemble a release's supported-platform manifest.
using Pkg.Artifacts
using Base.BinaryPlatforms
using Libdl
using TOML

const JULIA_PLATFORMS = Set([
    "x86_64-linux-gnu", "aarch64-linux-gnu", "x86_64-apple-darwin",
    "aarch64-apple-darwin", "x86_64-w64-mingw32",
])

function pack_native(platform_name, library, notices, output, download_base)
    platform_name in JULIA_PLATFORMS || error("Unsupported Julia platform: $platform_name")
    platform = parse(Platform, platform_name)
    extension = platform["os"] == "windows" ? "dll" : platform["os"] == "macos" ? "dylib" : "so"
    root = dirname(@__DIR__)
    hash = create_artifact() do directory
        mkpath(joinpath(directory, "lib"))
        cp(library, joinpath(directory, "lib", "datamonger_ffi.$extension"))
        mkpath(joinpath(directory, "include"))
        cp(joinpath(root, "crates", "datamonger-ffi", "include", "datamonger.h"),
           joinpath(directory, "include", "datamonger.h"))
        mkpath(joinpath(directory, "share", "licenses"))
        cp(joinpath(root, "LICENSE"), joinpath(directory, "share", "licenses", "LICENSE"))
        cp(notices, joinpath(directory, "share", "licenses", "COPYRIGHTS"))
    end
    mkpath(output)
    name = "datamonger-core.$platform_name.tar.gz"
    digest = archive_artifact(hash, joinpath(output, name))
    bind_artifact!(joinpath(output, "$platform_name.toml"), "datamonger_core", hash;
        platform, download_info=[(rstrip(download_base, '/') * "/$name", digest)],
        lazy=false, force=true)
end

function validate_manifest(path; complete=true)
    document = TOML.parsefile(path)
    entries = get(document, "datamonger_core", [])
    seen = Set{String}()
    releases = Set{String}()
    for entry in entries
        platform = Platform(entry["arch"], entry["os"]; libc=get(entry, "libc", nothing))
        name = triplet(platform)
        name in JULIA_PLATFORMS || error("Unsupported artifact platform $name")
        name in seen && error("Duplicate artifact platform $name")
        push!(seen, name)
        occursin(r"^[a-f0-9]{40}$", entry["git-tree-sha1"]) || error("Invalid tree hash")
        get(entry, "lazy", false) === false || error("Native artifacts must be installed with the package")
        downloads = entry["download"]
        length(downloads) == 1 || error("Expected one immutable archive per platform")
        download = only(downloads)
        occursin(r"^[a-f0-9]{64}$", download["sha256"]) || error("Invalid archive hash")
        startswith(download["url"], "https://github.com/jolars/datamonger/releases/download/datamonger-ffi-v") ||
            error("Native artifacts must come from a versioned native release")
        push!(releases, first(rsplit(download["url"], '/'; limit=2)))
        endswith(download["url"], "/datamonger-core.$name.tar.gz") || error("Archive name disagrees with platform")
    end
    length(releases) <= 1 || error("Native platforms must use the same release")
    complete && seen != JULIA_PLATFORMS && error("Missing native artifacts: $(setdiff(JULIA_PLATFORMS, seen))")
    return document
end

function merge_manifests(input, output)
    entries = Any[]
    for platform in sort(collect(JULIA_PLATFORMS))
        part = validate_manifest(joinpath(input, "$platform.toml"); complete=false)
        append!(entries, part["datamonger_core"])
    end
    open(output, "w") do io
        TOML.print(io, Dict("datamonger_core" => entries); sorted=true)
    end
    validate_manifest(output)
end

function stage_package(package, archives, destination)
    # Exercise the installable package without its checkout or local build stamp.
    cp(package, destination)
    rm(joinpath(destination, "Manifest.toml"); force=true)
    rm(joinpath(destination, "deps", "Artifacts.toml"); force=true)
    document = TOML.parsefile(joinpath(archives, "Artifacts.toml"))
    for entry in document["datamonger_core"], download in entry["download"]
        name = last(split(download["url"], '/'))
        archive = replace(abspath(joinpath(archives, name)), '\\' => '/')
        download["url"] = "file://" * (Sys.iswindows() ? "/" : "") * archive
    end
    open(joinpath(destination, "Artifacts.toml"), "w") do io
        TOML.print(io, document; sorted=true)
    end
end

function check_source(package)
    project = TOML.parsefile(joinpath(package, "Project.toml"))
    manifest = joinpath(package, "Artifacts.toml")
    # The unreleased bootstrap package can be built from source. Every version
    # eligible for registration must already pin the full native distribution.
    if project["version"] == "0.0.0" && isempty(TOML.parsefile(manifest))
        return false
    end
    validate_manifest(manifest)
    return true
end

function stage_release(package, destination)
    if check_source(package)
        cp(package, destination)
        rm(joinpath(destination, "Manifest.toml"); force=true)
        rm(joinpath(destination, "deps", "Artifacts.toml"); force=true)
    end
end

if abspath(PROGRAM_FILE) == @__FILE__
    command, args... = ARGS
    if command == "pack"
        pack_native(args...)
    elseif command == "merge"
        merge_manifests(args...)
    elseif command == "check"
        validate_manifest(only(args))
    elseif command == "stage"
        stage_package(args...)
    elseif command == "check-source"
        check_source(only(args))
    elseif command == "stage-release"
        stage_release(args...)
    else
        error("Usage: dm_julia_artifacts.jl pack|merge|check|stage ...")
    end
end
