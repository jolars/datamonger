use std::fmt::Display;
use std::io::{self, IsTerminal, Read, Write};
use std::time::Duration;

use anstream::{AutoStream, ColorChoice};
use indicatif::{ProgressBar, ProgressStyle};

pub(crate) struct Terminal {
    enabled: bool,
    color: bool,
}

impl Terminal {
    pub(crate) fn new(json: bool) -> Self {
        let enabled = !json && std::env::var_os("TERM").as_deref() != Some("dumb".as_ref());
        Self {
            enabled,
            color: enabled && std::env::var_os("NO_COLOR").is_none(),
        }
    }

    pub(crate) fn out(&self, args: std::fmt::Arguments<'_>) {
        let stdout = io::stdout();
        let choice = self.choice(stdout.is_terminal());
        writeln!(AutoStream::new(stdout.lock(), choice), "{args}").expect("write stdout");
    }

    pub(crate) fn error(&self, category: &str, message: &str) {
        let stderr = io::stderr();
        let choice = self.choice(stderr.is_terminal());
        let _ = writeln!(
            AutoStream::new(stderr.lock(), choice),
            "\x1b[31merror[{category}]\x1b[0m: {message}"
        );
    }

    fn choice(&self, is_terminal: bool) -> ColorChoice {
        if self.color && is_terminal {
            ColorChoice::Auto
        } else {
            ColorChoice::Never
        }
    }

    pub(crate) fn stage(&self, action: &str, subject: &str, size: Option<u64>) -> Stage {
        let bar = (self.enabled && io::stderr().is_terminal()).then(|| {
            let bar = match size.filter(|size| *size > 0) {
                Some(size) => ProgressBar::new(size),
                None => ProgressBar::new_spinner(),
            };
            if bar.is_hidden() {
                return None;
            }
            let template = match (size.unwrap_or(0) > 0, self.color) {
                (true, true) => "{msg} [{bar:24.cyan/blue}] {bytes}/{total_bytes}",
                (true, false) => "{msg} [{bar:24}] {bytes}/{total_bytes}",
                (false, true) => "{spinner:.cyan} {msg}",
                (false, false) => "{spinner} {msg}",
            };
            bar.set_style(ProgressStyle::with_template(template).expect("valid progress template"));
            bar.set_message(format!("{action} {subject}"));
            bar.enable_steady_tick(Duration::from_millis(100));
            bar.force_draw();
            Some(bar)
        });
        Stage(bar.flatten())
    }
}

pub(crate) fn cyan(value: impl Display) -> impl Display {
    styled(36, value)
}

pub(crate) fn dataset_label(id: &str) -> String {
    let Some((source, rest)) = id.split_once(':') else {
        return styled(36, id);
    };
    let Some((name, version)) = rest.rsplit_once('@') else {
        return styled(36, id);
    };
    format!(
        "{}:{}@{}",
        styled(35, source),
        cyan(name),
        styled(33, version)
    )
}

pub(crate) fn styled(color: u8, value: impl Display) -> String {
    format!("\x1b[{color}m{value}\x1b[0m")
}

pub(crate) struct Stage(Option<ProgressBar>);

impl Stage {
    pub(crate) fn advance(&self, count: u64) {
        if let Some(bar) = &self.0 {
            bar.inc(count);
        }
    }

    pub(crate) fn copy(
        stage: Option<&Self>,
        input: &mut impl Read,
        output: &mut impl Write,
    ) -> io::Result<u64> {
        match stage.and_then(|stage| stage.0.as_ref()) {
            Some(bar) => io::copy(input, &mut bar.wrap_write(output)),
            None => io::copy(input, output),
        }
    }
}

impl Drop for Stage {
    fn drop(&mut self) {
        if let Some(bar) = &self.0 {
            bar.finish_and_clear();
        }
    }
}
