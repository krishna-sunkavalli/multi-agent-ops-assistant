# Next Steps

After successful deployment, here are recommended next steps:

## 1. Verify the deployment
- Navigate to the app URL printed at the end of `azd up`
- Open the ShiftIQ chat interface and ask: "How are we doing?"
- Run the e2e test suite: `python tests/e2e_agent_test.py <app-url>`

## 2. Explore the agents
- Check the Foundry portal → Agents page to see all registered agents
- Review agent configs in `src/agents/configs/` to understand routing and tool bindings
- Try different questions to trigger each specialist (see demo guide: `docs/demo-guide.md`)

## 3. Set up CI/CD
- Push the repo to GitHub
- Configure the GitHub Actions secrets and variables listed in `.github/workflows/build-and-deploy.yml`
- First push to `main` triggers the build → push to ghcr.io → deploy pipeline

## 4. Customize for your scenario
- Modify `database/schema.sql` and `database/seed-data.sql` for your domain data
- Add or edit agent configs in `src/agents/configs/`
- Add operational documents to `operational-docs/` (auto-indexed on deploy)

## 5. Production readiness
See the [future features doc](docs/future-features.md) for roadmap items including:
- User authentication (Microsoft Entra ID)
- Per-user conversation persistence (Azure Cosmos DB)
- Multi-tenant data isolation
- Enhanced NL2SQL pipeline
