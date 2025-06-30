import OpenAI from 'openai';

type User = {
  name: string;
  age: number;
  email: string;
};

const openai = new OpenAI({
  baseURL: `${process.env.WORKFLOWAI_API_URL}/v1`,
  apiKey: process.env.WORKFLOWAI_API_KEY,
});

async function* extractUser(content: string): AsyncGenerator<User> {
  const completion = await openai.chat.completions.create({
    model: 'gpt-4',
    messages: [
      { role: 'system', content: 'Extract the user from the following message' },
      {
        role: 'user',
        content: content,
      },
    ],
    response_format: {
      type: 'json_schema',
      json_schema: {
        name: 'User',
        schema: {
          properties: {
            name: { type: 'string' },
            age: { type: 'number' },
            email: { type: 'string' },
          },
        },
      },
    },
    stream: true,
    stream_options: {
      //@ts-expect-error - valid_json_chunks is not supported by OpenAI
      valid_json_chunks: true,
    },
  });

  for await (const chunk of completion) {
    if (chunk.choices[0].delta.content) {
      yield JSON.parse(chunk.choices[0].delta.content);
    }
  }
}

async function main() {
  for await (const user of extractUser('John Doe is 30 years old and his email is john.doe@example.com')) {
    console.log(user);
  }
}

main();
