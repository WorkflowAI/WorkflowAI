# Integration Tests

Integration tests:

- test the API from the outside by calling endpoints
- use containerized dependencies when possible, like MongoDB, Redis, etc.
- disable analytics tracking to avoid adding noise
- DO NOT mock any external http calls like calls to providers

Integration tests are slow and costly and therefore ran only on merges on the main branch. See the [API Quality workflow](/.github/workflows/.api-quality.yml) for more details.
