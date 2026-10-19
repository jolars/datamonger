use std::error::Error;
use std::fs;
use std::path::Path;

// Share the parser without exposing an API or linking documentation tools into the CLI.
#[allow(dead_code)]
#[path = "../src/cli.rs"]
mod cli;

fn main() -> Result<(), Box<dyn Error>> {
    let check = match std::env::args().skip(1).collect::<Vec<_>>().as_slice() {
        [] => false,
        [arg] if arg == "--check" => true,
        _ => return Err("usage: generate_cli_docs [--check]".into()),
    };
    let options = clapdown::Options::new()
        .flavor(clapdown::Flavor::CommonMark)
        .title("Command-line reference");
    let markdown = clapdown::render_from::<cli::Cli>(&options);
    let output =
        Path::new(env!("CARGO_MANIFEST_DIR")).join("../../documentation/pages/cli-reference.md");
    if check {
        if fs::read_to_string(&output)?.replace("\r\n", "\n") != markdown {
            return Err(
                "CLI reference is stale; run cargo run --locked --example generate_cli_docs \
                 from packages/cli"
                    .into(),
            );
        }
    } else {
        fs::write(output, markdown)?;
    }
    Ok(())
}
