# Integration Scripts for Rust

## Requirements

Rust must be installed on your machine. You can install it using [rustup](https://rustup.rs/).

```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
```

## Structure

- All scripts must be added to the `src` directory.
- A reference to the script must be added to the `Cargo.toml` file under the `[[bin]]` section.
- Each script must contain a `main` function that is the entry point of the script.

At the time of writing, the `async-openai` does not allow to override the openai base URL using an
environment variable si the script must be modified to use the `WORKFLOWAI_API_URL` environment variable.

Below is an example of how to configure the client.

```rust
let api_key = env::var("WORKFLOWAI_API_KEY").context("WORKFLOWAI_API_KEY must be set")?;
let api_base = env::var("WORKFLOWAI_API_URL").context("WORKFLOWAI_API_URL must be set")?;
let config = OpenAIConfig::new().with_api_base(api_base).with_api_key(api_key);
let client = Client::with_config(config);
```

Scripts can then be executed using `cargo run <script name>`.

## Running the script

```bash
cargo run --bin chat
```
