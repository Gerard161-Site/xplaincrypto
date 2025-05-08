# Optimization Plan for XplainCrypto Research Workflow

This document outlines the plan to improve the research speed and cost-effectiveness of XplainCrypto while maintaining data integrity.

## Progress Tracking

| Phase | Task | Status | Date | Notes |
|-------|------|--------|------|-------|
| Pre-optimization | Fix cache directory structure issues | ✅ Completed | May 8, 2023 | Fixed issues with cache files being created in incorrect locations |
| Pre-optimization | Fix CoinGecko caching | ✅ Completed | May 8, 2023 | Ensured CoinGecko cache files are stored in project-specific directories |
| Pre-optimization | Fix tokenomics caching | ✅ Completed | May 8, 2023 | Fixed redundant cache files in tokenomics server |
| Phase 1 | Implement RAG result caching | ✅ Completed | May 8, 2023 | Added caching layer for RAG results to avoid redundant vector searches. Performance test showed ~896x average speedup! |
| Phase 1 | Implement cache cleanup for scale | ✅ Completed | May 8, 2023 | Added LRU cache cleanup to handle thousands of projects with automatic maintenance |
| Phase 1 | Enhance existing RAG system | 🔄 Planned | - | - |
| Phase 1 | Batch Tavily searches | 🔄 Planned | - | - |
| Phase 2 | Single API calls for data sources | 🔄 Planned | - | - |
| Phase 2 | Optimize state management | 🔄 Planned | - | - |
| Phase 3 | Implement report-driven workflow | �� Planned | - | - |
| Phase 2 | Implement dynamic TTL caching | 🔄 Planned | - | - |
| Phase 2 | Add two-level cache system | 🔄 Planned | - | - |
| Phase 3 | Create dependency-aware workflow manager | 🔄 Planned | - | - |
| Phase 3 | Implement cascading fallback system | 🔄 Planned | - | - |
| Phase 3 | Add performance monitoring | 🔄 Planned | - | - |

## Scaling Considerations

XplainCrypto needs to handle research for any cryptocurrency project (10,000+ potential projects), not just the ones we test with like Ondo. This introduces several key considerations for our optimization plan:

### Cache Management at Scale
- **Disk Space Management**: With thousands of projects, each with multiple queries and data sources, cache size could grow rapidly. We need to implement:
  - Automatic cache cleanup for least recently used (LRU) entries
  - Maximum cache size limits per project (configurable in `app_config.json`)
  - Cache expiration based on data volatility (e.g., price data expires faster than tokenomics data)

### Optimizing for New Projects
- **Cold Start Performance**: First-time queries for new projects will have no cache, requiring:
  - Efficient RAG retrieval with minimal API calls
  - Parallel processing of initial data gathering
  - Background pre-caching of common data points once a project is first researched

### Resource Utilization
- **API Rate Limiting**: With many concurrent users researching different projects:
  - Implement token bucket rate limiting for external APIs
  - Prioritize cache hits over fresh data when approaching rate limits
  - Queue and batch similar requests across different projects

### Monitoring and Analytics
- **Usage Patterns**: Track which projects and query types are most common
- **Cache Hit Ratios**: Monitor effectiveness of caching by project
- **Resource Consumption**: Track API usage, processing time, and storage requirements by project

These scaling considerations will be incorporated into each phase of our optimization plan to ensure the system remains efficient and cost-effective as usage grows.

## 1. RAG-Driven Endpoint Selection

**Current Implementation:** 
The system uses RAG with Pinecone for endpoint selection:
- `RAGRetriever` queries Pinecone to select MCP endpoints
- `vector_store.py` interfaces with Pinecone to store endpoint metadata
- Some hardcoded routing logic exists in `client_manager.py`

**Proposed Improvement:**
- Enhance the existing RAG system to better utilize query context
- Implement more sophisticated embedding models for better endpoint matching
- Add a caching layer specifically for RAG results to avoid redundant vector searches
- Reduce hardcoded endpoint mappings in `client_manager.py`

```python
class EnhancedRAGRetriever:
    def __init__(self, vector_store):
        self.vector_store = vector_store
        self.cache_manager = CacheManager(project_name="system", logger=logger)
        
    async def get_endpoints_for_query(self, query, project_name):
        # Check cache first
        cache_key = f"{query.lower().replace(' ', '_')}"
        cached_endpoints = self.cache_manager.load("rag", "endpoints", cache_key)
        if cached_endpoints:
            return cached_endpoints
            
        # Query vector store
        endpoints = await self.vector_store.query(query)
        
        # Cache results
        self.cache_manager.save(endpoints, "rag", "endpoints", cache_key)
        return endpoints
```

## 2. Batch Processing for API Calls

**Current Implementation:** 
Each endpoint is called individually, even when multiple data points are needed from the same source.

**Proposed Improvement:**
- Aggregate all required endpoints by source before making API calls
- Implement a batching system for Tavily searches (3 queries at a time)
- Create a dependency graph to determine the optimal order of API calls

```python
async def batch_process_endpoints(self, endpoints, project_name):
    # Group endpoints by source
    endpoints_by_source = {}
    for endpoint in endpoints:
        source = endpoint.split("://")[1].split("/")[0]
        if source not in endpoints_by_source:
            endpoints_by_source[source] = []
        endpoints_by_source[source].append(endpoint)
    
    # Process each source with a single API call when possible
    results = {}
    for source, source_endpoints in endpoints_by_source.items():
        if source == "tavily":
            results[source] = await self._process_tavily_batch(source_endpoints, project_name)
        else:
            results[source] = await self._process_source_batch(source, source_endpoints, project_name)
            
    return results
```

## 3. Tavily Query Batching

**Current Implementation:** 
Each Tavily search is executed independently.

**Proposed Improvement:**
- Implement a batching system for Tavily searches
- Process 3 queries at a time to respect rate limits
- Deduplicate similar queries to avoid redundant searches

```python
async def _process_tavily_batch(self, endpoints, project_name, batch_size=3):
    queries = [self._extract_query(endpoint) for endpoint in endpoints]
    unique_queries = list(set(queries))  # Remove duplicates
    
    results = {}
    for i in range(0, len(unique_queries), batch_size):
        batch = unique_queries[i:i+batch_size]
        batch_results = await asyncio.gather(*[
            self.client_manager.fetch_data(
                f"data://tavily/research/{query}", 
                {"project_name": project_name}
            ) for query in batch
        ])
        
        # Map results back to queries
        for query, result in zip(batch, batch_results):
            results[query] = result
            
    return results
```

## 4. Enhanced State Management

**Current Implementation:** 
State is managed but not optimized for section-specific data access.

**Proposed Improvement:**
- Restructure ResearchState to better align with report_config.json sections
- Add metadata about data sources and confidence levels
- Implement a versioning system for state to track changes

```python
class ResearchState:
    def __init__(self, project_name):
        self.project_name = project_name
        self.data = {}  # Section-specific data
        self.multi_source_data = {}  # Source-specific data (shared across sections)
        self.visualization_data = {}  # Data specifically for visualizations
        self.errors = []
        self.cache_paths = {}
        self.metadata = {
            "version": "1.0",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "data_sources": []
        }
        
    def add_data(self, section_name, source, data):
        if section_name not in self.data:
            self.data[section_name] = {}
        self.data[section_name][source] = data
        
        # Also store in multi_source_data for cross-section access
        if source not in self.multi_source_data:
            self.multi_source_data[source] = {}
        self.multi_source_data[source].update(data)
        
        # Update metadata
        if source not in self.metadata["data_sources"]:
            self.metadata["data_sources"].append(source)
        self.metadata["updated_at"] = datetime.now().isoformat()
```

## 5. Intelligent Caching Strategy

**Current Implementation:** 
Basic caching with fixed TTLs by source.

**Proposed Improvement:**
- Implement dynamic TTLs based on data volatility
- Add cache invalidation triggers for significant market events
- Implement a two-level cache (memory and disk) for frequently accessed data

```python
class EnhancedCacheManager(CacheManager):
    # Dynamic TTL calculation based on data volatility
    def calculate_ttl(self, source, endpoint, data):
        base_ttl = self.TTL_BY_SOURCE.get(source, 24)
        
        # Adjust TTL based on data volatility
        if source == "coingecko" and "price" in endpoint:
            # Price data is highly volatile
            return base_ttl * 0.5  # Half the default TTL
        elif source == "defillama" and "tvl" in endpoint:
            # TVL changes less frequently
            return base_ttl * 1.5  # 1.5x the default TTL
            
        return base_ttl
        
    def save(self, data, source, endpoint, query, **kwargs):
        # Calculate dynamic TTL
        ttl_hours = self.calculate_ttl(source, endpoint, data)
        return super().save_to_cache(data, source, endpoint, query, ttl_hours=ttl_hours)
```

## 6. Fallback Mechanism Enhancement

**Current Implementation:** 
Limited fallback options when data sources fail.

**Proposed Improvement:**
- Implement a cascading fallback system
- Try multiple alternative sources before resorting to Hugging Face
- Add data quality scores to indicate source reliability

```python
async def get_data_with_fallbacks(self, endpoint, project_name):
    # Try primary source
    result = await self.client_manager.fetch_data(endpoint, {"project_name": project_name})
    
    # Check if result has error
    if "error" in result:
        logger.warning(f"Primary source failed for {endpoint}, trying alternatives")
        
        # Try alternative sources based on endpoint type
        alternatives = self._get_alternative_sources(endpoint)
        for alt_endpoint in alternatives:
            alt_result = await self.client_manager.fetch_data(alt_endpoint, {"project_name": project_name})
            if "error" not in alt_result:
                # Mark as from alternative source
                alt_result["source"] = f"alternative:{alt_endpoint}"
                alt_result["primary_source_failed"] = True
                return alt_result
                
        # If all alternatives fail, try Hugging Face as last resort
        hf_result = await self.client_manager.fetch_data(
            f"data://huggingface/{project_name}", 
            {"query": endpoint, "project_name": project_name}
        )
        
        if "error" not in hf_result:
            hf_result["source"] = "fallback:huggingface"
            hf_result["primary_source_failed"] = True
            return hf_result
            
        # All sources failed, return data_unavailable
        return {
            "data_unavailable": True,
            "source": "unavailable",
            "error": result["error"],
            "endpoint": endpoint
        }
        
    return result
```

## 7. Workflow Orchestration Improvements

**Current Implementation:** 
Sequential processing of endpoints.

**Proposed Improvement:**
- Implement a dependency-aware workflow manager
- Process independent endpoints in parallel
- Add progress tracking for long-running operations

```python
class WorkflowManager:
    def __init__(self, client_manager, rag_retriever):
        self.client_manager = client_manager
        self.rag_retriever = rag_retriever
        
    async def run_research_workflow(self, project_name):
        # Initialize state
        state = ResearchState(project_name)
        
        # Load report config
        report_config = self._load_report_config()
        
        # Collect all required endpoints using RAG
        all_endpoints = await self._collect_endpoints(report_config, project_name)
        
        # Build dependency graph
        dependency_graph = self._build_dependency_graph(all_endpoints)
        
        # Process endpoints in optimal order
        results = await self._process_endpoints_with_dependencies(dependency_graph, project_name)
        
        # Update state with results
        self._update_state(state, results, report_config)
        
        # Save state to cache
        self._save_state(state)
        
        return state
```

## 8. Performance Monitoring

**Current Implementation:** 
Basic logging without performance metrics.

**Proposed Improvement:**
- Add timing metrics for each phase of the research process
- Implement a performance dashboard for monitoring API calls and processing time
- Set up alerts for slow operations or high API usage

```python
class PerformanceTracker:
    def __init__(self):
        self.metrics = {}
        
    @contextmanager
    def track(self, operation_name):
        start_time = time.time()
        try:
            yield
        finally:
            elapsed = time.time() - start_time
            if operation_name not in self.metrics:
                self.metrics[operation_name] = []
            self.metrics[operation_name].append(elapsed)
            logger.info(f"Operation {operation_name} completed in {elapsed:.2f}s")
            
    def get_summary(self):
        summary = {}
        for op, times in self.metrics.items():
            summary[op] = {
                "count": len(times),
                "total_time": sum(times),
                "avg_time": sum(times) / len(times) if times else 0,
                "min_time": min(times) if times else 0,
                "max_time": max(times) if times else 0
            }
        return summary
```

## Implementation Strategy

To implement these improvements while maintaining what's working, we recommend a phased approach:

### Phase 1: RAG Integration and Endpoint Batching
1. Enhance the existing RAG system
2. Implement endpoint batching for each source
3. Add Tavily query batching

### Phase 2: Enhanced State and Caching
1. Enhance the ResearchState structure
2. Implement the dynamic TTL caching strategy
3. Add the two-level cache system

### Phase 3: Workflow Optimization
1. Create the dependency-aware workflow manager
2. Implement the cascading fallback system
3. Add performance monitoring

This approach allows us to incrementally improve the system without disrupting the current functionality, while significantly enhancing research speed and cost-effectiveness. 