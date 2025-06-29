# Documentation Inconsistencies Report

**Date**: Generated during documentation review  
**Scope**: `/docsv2` directory only  
**Summary**: Found multiple categories of inconsistencies that impact user experience and documentation quality.

---

## 🚨 Critical Issues

### 1. API Base URL Inconsistencies

**Problem**: Documentation uses two different base URLs inconsistently across files.

**Inconsistent Usage**:
- `https://api.workflowai.com` - Used in MCP examples and some endpoints
- `https://run.workflowai.com` - Used in most API examples and inference

**Examples**:
- **MCP Configuration** (`index.mdx:41`): `"url": "https://api.workflowai.com/mcp/"`
- **Inference Examples** (`models.mdx:27`): `base_url="https://run.workflowai.com/v1"`
- **Foundation Examples** (`foundations.mdx:23`): `base_url="https://api.workflowai.com/v1"`

**Impact**: Users may get confused about which endpoint to use, leading to API call failures.

**Recommendation**: Standardize on one base URL or clearly document when each should be used.

---

### 2. Parameter Naming Inconsistencies

**Problem**: Agent ID parameter uses multiple naming conventions across the documentation.

**Inconsistent Formats**:
- `agent_id` (Python style) - Most common
- `agentId` (JavaScript camelCase) - Used in some JS examples
- `agentID` - Mentioned in TODO comment

**Examples**:
- **Python**: `metadata={"agent_id": "my-agent"}` (foundations.mdx:58)
- **JavaScript**: `metadata: { agentId: "email-analyzer" }` (input-variables.mdx:56)
- **TODO Comment**: "check with @guillaume to confirm `agentID`, `agent_id` or `agentId` in Typescript" (models.mdx:108)

**Impact**: Developers copying examples may use wrong parameter names causing API errors.

**Recommendation**: Establish consistent naming conventions for each language and update all examples.

---

### 3. API Key Variable Naming Inconsistencies

**Problem**: Multiple different environment variable names used for API keys.

**Inconsistent Names**:
- `WORKFLOWAI_API_KEY`
- `YOUR_WORKFLOWAI_API_KEY`
- `YOUR_API_KEY_HERE`
- `YOUR_API_KEY`

**Examples**:
- **Authentication**: `Authorization: Bearer WORKFLOWAI_API_KEY` (authentication.mdx:13)
- **Models**: `api_key="YOUR_WORKFLOWAI_API_KEY"` (models.mdx:26)
- **MCP Setup**: `Bearer YOUR_API_KEY_HERE` (index.mdx:63)

**Impact**: Users may be unclear about the correct environment variable name to use.

**Recommendation**: Standardize on one variable name pattern (suggest `WORKFLOWAI_API_KEY`).

---

## ⚠️ Documentation Quality Issues

### 4. Extensive TODO Items

**Problem**: 40+ TODO items throughout documentation indicating incomplete sections.

**Categories of TODOs**:
- Missing screenshots/videos (12 items)
- Incomplete API documentation (8 items)
- Pending technical clarifications (15 items)
- Missing feature implementations (10+ items)

**Critical Examples**:
- **MCP Installation**: "**TODO:** Add a direct link to install the MCP." (index.mdx:27)
- **API Errors**: "> TODO: check with @guillaume" (api-errors.mdx:8)
- **Structured Outputs**: Multiple TODOs for syntax checking (structured-outputs.mdx:292-372)

**Impact**: Users encounter incomplete information, reducing documentation usefulness.

**Recommendation**: Prioritize completion of high-impact TODOs, especially those in user-facing sections.

---

### 5. Navigation Structure Inconsistencies

**Problem**: Navigation metadata doesn't align with actual content organization.

**Issues Found**:
- **Missing Quickstarts**: Main nav doesn't include quickstarts section despite having quickstart content
- **Private Files**: Many `.private.mdx` files in navigation but marked as unpublished
- **Broken References**: Some meta.json references point to non-existent files

**Example**: 
- Quickstarts exist (`quickstarts/openai-python.private.mdx`) but not in main navigation
- Observability shows `insights` and `search` in nav but files are marked private

**Impact**: Users cannot navigate to available content, creating discovery issues.

**Recommendation**: Audit navigation structure and align with content availability.

---

## 📝 Content Inconsistencies

### 6. Terminology Variations

**Problem**: Inconsistent use of key terms throughout documentation.

**Examples**:
- **WorkflowAI vs Workflow AI**: Used inconsistently
- **Agent vs Task**: Sometimes used interchangeably 
- **Schema vs Structure**: Mixed usage in structured outputs
- **Run vs Request**: Inconsistent terminology for API calls

**Impact**: Creates confusion about platform concepts and architecture.

**Recommendation**: Create terminology glossary and enforce consistent usage.

---

### 7. Code Example Inconsistencies

**Problem**: Code examples show different patterns for the same functionality.

**Inconsistencies**:
- **Import statements**: Some examples include imports, others don't
- **Error handling**: Inconsistent across examples
- **Comment styles**: Mixed `#` and `//` in some files
- **Authentication methods**: Different patterns shown

**Example**: Some examples show full client setup, others assume it's already configured.

**Impact**: Users may struggle to understand complete implementation requirements.

**Recommendation**: Standardize code example format and ensure completeness.

---

## 🔧 Technical Issues

### 8. Endpoint Documentation Misalignment

**Problem**: Different endpoint patterns mentioned for similar functionality.

**Examples**:
- Standard: `https://run.workflowai.com/v1/chat/completions`
- Alternative: `https://run.workflowai.com/v1/[org-id]/tasks/[agent-id]/schemas/[schema-id]/run`

**Impact**: Unclear which endpoints to use for specific use cases.

**Recommendation**: Clearly document when each endpoint pattern should be used.

---

### 9. Feature Availability Confusion

**Problem**: Documentation mentions features that may not be available or are in beta.

**Examples**:
- **MCP Warning**: "This guide is a work in progress and is not ready to be published" (mcp.mdx)
- **Private Files**: Many features documented in `.private.mdx` files
- **Beta Features**: Some features mentioned without clear beta status

**Impact**: Users may try to use unavailable features.

**Recommendation**: Clearly mark feature availability status throughout documentation.

---

## 📊 Impact Assessment

### High Priority (Fix Immediately)
1. API Base URL inconsistencies
2. Parameter naming inconsistencies  
3. Critical TODO items in user-facing sections

### Medium Priority (Fix Soon)
4. API key variable naming
5. Navigation structure issues
6. Code example standardization

### Low Priority (Address Over Time)
7. Terminology standardization
8. Complete TODO items
9. Feature availability clarification

---

## 🔍 Recommendations Summary

1. **Establish Style Guide**: Create comprehensive documentation style guide
2. **Audit API Endpoints**: Clarify when to use each base URL pattern
3. **Standardize Examples**: Ensure all code examples follow consistent patterns
4. **Complete TODOs**: Prioritize completing user-facing incomplete sections
5. **Fix Navigation**: Align navigation with actual content availability
6. **Review Process**: Implement review process to catch inconsistencies before publication

---

## 📁 Files Reviewed

Total files analyzed: 50+ MDX files across:
- `/content/docs/` (main documentation)
- `/content/docs/quickstarts/` (getting started guides) 
- `/content/docs/reference/` (API reference)
- `/content/docs/observability/` (monitoring docs)
- `/content/docs/inference/` (API usage docs)
- `/content/docs/agents/` (agent-specific docs)
- Navigation files (`meta.json`)

**Report generated**: Automated analysis of `/docsv2` directory only.