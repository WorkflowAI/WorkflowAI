# Contributing

## Guidelines

### Deployments

This project uses Github Action for CI / CD.

- the `main` branch is the central branch that contains the latest version of WorkflowAI. Any merge on main triggers
  a deployment to the staging environment
- any pull request that targets main triggers a quality check of the client and api portions based on
  the changes. The quality checks are required to pass before merging to main.
- Releases (`release/*`) and hotfix (`hotfix/*`) trigger deploys to the preview environment
- Deployment to the production environment are triggered by versioned tags.

### Branch flow

#### Feature or fix

A traditional feature or fix starts by creating a branch from `main`and results in a pull request on the `main` branch.
By convention, feature branch names should start with the name of the person creating the branch.

#### Release process

Releases are the process of deploying the code currently living in the staging env to production. The flow
starts with the creation of the `release/<release-date>` branch which triggers a deploy to the preview environment. A
PR from the release branch into main should be created as well.
This allows `main` to continue changing independently while the release is being QAed. Any fix for the release
should be a pull request into the release branch.

When the release is ready, the appropriate tags and github releases should be created from the release branch to
trigger deployments to the production environment. Once everything is ok, the branch should be merged to `main`.

#### Hotfix process

A hotfix allows fixing bugs in production without having to push changes to the development environment first.
A hotfix branch should be created from the latest tag and a PR targeting main should be created. The flow is then the
same as the release process.

### Code style

All client code is formatted using Prettier. Run `yarn prettier-check` before committing
changes to ensure your code follows the repository style.
