# Dynamic Documentation Discovery Implementation

## Problem Solved
The MCP `search_documentation` tool previously maintained a hardcoded list of available documentation pages in its docstring. This created maintenance burden, sync issues, and scalability problems as documentation grew.

## Solution Overview
Implemented a dynamic documentation discovery system that:

1. **Automatically scans** the `docsv2/content/docs/` directory structure
2. **Parses MDX frontmatter** to extract `title` and `summary` fields  
3. **Dynamically generates** the available pages description for the MCP tool
4. **Eliminates manual maintenance** of hardcoded page lists

## Implementation Details

### Core Components

#### 1. `_doc_discovery.py` - Documentation Discovery Module
- **`DocPage`**: Dataclass representing a documentation page with metadata
- **`DocDiscovery`**: Main class handling directory scanning and MDX parsing
- **Key features**:
  - YAML frontmatter parsing with error handling
  - Category mapping (e.g., "use-cases" → "Use Cases")  
  - Caching for performance
  - Filtering (skips partials directory and files without frontmatter)

#### 2. `mcp_server.py` - Updated MCP Server
- **`description_for_search_documentation()`**: Dynamic description generator
- **Updated tool registration**: Uses dynamic description instead of hardcoded docstring
- **Clean separation**: Removed 100+ lines of hardcoded documentation

### Key Features

#### Automatic Directory Scanning
```python
# Finds all MDX files in docsv2/content/docs/
mdx_files = list(self.docs_root.rglob("*.mdx"))
```

#### Frontmatter Parsing
```python
# Extracts YAML frontmatter with regex
frontmatter_pattern = r'^---\s*\n(.*?)\n---\s*\n'
frontmatter = yaml.safe_load(match.group(1))
```

#### Smart Path Handling
- Root index → "index"
- Directory index → parent directory name  
- Regular files → full relative path
- Categories assigned based on top-level directory

#### Caching & Performance
- Pages cached after first scan
- Force refresh available for updates
- Error-tolerant (continues processing if individual files fail)

## Testing Results

The implementation successfully discovered **69 documentation pages** from the actual file system:

```
Found 69 documentation pages
  agents (Agents): Overview
  agents/mcp (Agents): Model Context Protocol (MCP)  
  agents/memory (Agents): Memory
  agents/tools (Agents): Tools
  ai-engineer (AI Engineer): Setup
  ...
```

Generated dynamic description with **95 lines** organized by category:
- **AI Engineer**
- **API Reference** 
- **Agents**
- **Components**
- **Deployments**
- **Evaluations**
- **Getting Started**
- **Inference**
- **Observability** 
- **Playground**
- **Quickstarts**
- **Use Cases**

## Benefits Achieved

### ✅ **Maintenance Burden Eliminated**
- No more manual updates to hardcoded lists
- Documentation changes automatically reflected

### ✅ **Sync Issues Resolved** 
- Tool description always matches actual file structure
- No risk of outdated hardcoded information

### ✅ **Scalability Improved**
- System scales automatically with documentation growth
- New categories and pages discovered automatically

### ✅ **Developer Experience Enhanced**
- Clean separation of concerns
- Reusable utility module
- Comprehensive error handling

## Files Modified

1. **`api/api/routers/mcp/_doc_discovery.py`** - New utility module (178 lines)
2. **`api/api/routers/mcp/mcp_server.py`** - Updated to use dynamic system
3. **`api/api/routers/mcp/_doc_discovery_test.py`** - Comprehensive test suite (173 lines)

## Usage

The system works transparently - no changes needed for MCP clients. The `search_documentation` tool now automatically reflects the current documentation structure:

```python
# Dynamic discovery in action
doc_discovery = get_doc_discovery()
available_pages = doc_discovery.generate_available_pages_description()
```

## Future Enhancements

The modular design supports potential future improvements:
- **Metadata enrichment**: Extract additional frontmatter fields
- **Categorization refinement**: More sophisticated category logic
- **Performance optimization**: File watching for real-time updates
- **Validation**: Ensure all pages have required frontmatter

## Conclusion

The dynamic documentation discovery system successfully eliminates the maintenance burden of hardcoded documentation lists while improving accuracy and scalability. The MCP tool now automatically stays in sync with the actual documentation structure without requiring code changes.