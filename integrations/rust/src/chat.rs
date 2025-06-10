use std::error::Error;

use async_openai::{
    types::{
        ChatCompletionRequestAssistantMessageArgs, ChatCompletionRequestSystemMessageArgs,
        ChatCompletionRequestUserMessageArgs, CreateChatCompletionRequestArgs,
    },
    config::OpenAIConfig,
    Client,
};
use std::env;
use anyhow::Context;

#[tokio::main]
async fn main() -> Result<(), Box<dyn Error>> {
    let api_key = env::var("WORKFLOWAI_API_KEY").context("WORKFLOWAI_API_KEY must be set")?;
    let api_base = env::var("WORKFLOWAI_API_URL").context("WORKFLOWAI_API_URL must be set")?;
    let config = OpenAIConfig::new().with_api_base(api_base + "/v1").with_api_key(api_key);
    let client = Client::with_config(config);

    let request = CreateChatCompletionRequestArgs::default()
        .max_tokens(512u32)
        .model("gpt-3.5-turbo")
        .messages([
            ChatCompletionRequestSystemMessageArgs::default()
                .content("You are a helpful assistant.")
                .build()?
                .into(),
            ChatCompletionRequestUserMessageArgs::default()
                .content("Who won the world series in 2020?")
                .build()?
                .into(),
            ChatCompletionRequestAssistantMessageArgs::default()
                .content("The Los Angeles Dodgers won the World Series in 2020.")
                .build()?
                .into(),
            ChatCompletionRequestUserMessageArgs::default()
                .content("Where was it played?")
                .build()?
                .into(),
        ])
        .build()?;

    println!("{}", serde_json::to_string(&request).unwrap());

    let response = client.chat().create(request).await?;

    println!("\nResponse:\n");
    for choice in response.choices {
        println!(
            "{}: Role: {}  Content: {:?}",
            choice.index, choice.message.role, choice.message.content
        );
    }

    Ok(())
}
