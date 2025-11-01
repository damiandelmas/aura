#!/usr/bin/env python3
"""
Modular Search System - Support multiple models, collections, and configurations
"""

import sys
import argparse
import json
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
from datetime import datetime
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue
from sentence_transformers import SentenceTransformer
import re

logger = logging.getLogger(__name__)

from .config import config

class SearchConfig:
    """Configuration for different search setups"""
    def __init__(self, name: str, model_name: str, collection_name: str, 
                 vector_name: str, dimensions: int):
        self.name = name
        self.model_name = model_name
        self.collection_name = collection_name
        self.vector_name = vector_name
        self.dimensions = dimensions
    
    @classmethod
    def from_dict(cls, data: dict):
        return cls(**data)
    
    def to_dict(self) -> dict:
        return {
            'name': self.name,
            'model_name': self.model_name,
            'collection_name': self.collection_name,
            'vector_name': self.vector_name,
            'dimensions': self.dimensions
        }

class ModularSearch:
    """Search system that supports multiple models and collections"""

    def __init__(self, config_path: str = "search_configs.json"):
        """Initialize the modular search system.

        Sets up a Qdrant client connection, loads search configurations from disk,
        and initializes a model cache for efficient reuse of embedding models.

        Args:
            config_path: Path to JSON file containing search configurations.
                        Defaults to "search_configs.json" in current directory.

        Returns:
            None

        Attributes:
            client: QdrantClient instance connected to configured Qdrant port
            config_path: Path object for the configuration file location
            configs: Dictionary mapping config names to SearchConfig objects
            loaded_models: Dictionary caching loaded SentenceTransformer models
                         by config name for performance
        """
        self.client = QdrantClient(host="localhost", port=config.qdrant_port)
        self.config_path = Path(config_path)
        self.configs = self.load_configs()
        self.loaded_models = {}  # Cache loaded models
    
    def load_configs(self) -> Dict[str, SearchConfig]:
        """Load available search configurations.

        Reads search configurations from the JSON config file. If the file doesn't
        exist, creates it with a set of default configurations for common embedding
        models (MiniLM, MPNet, CodeBERT).

        Returns:
            Dictionary mapping configuration names (str) to SearchConfig objects.
            Each config specifies a model, collection, vector name, and dimensions.

        Notes:
            - Default configs include: current, mpnet, codebert, minilm_l12
            - All configs use configured Qdrant port for connection
            - Config file is created automatically if missing
        """
        if not self.config_path.exists():
            # Create default configs
            default_configs = {
                'current': SearchConfig(
                    name='current',
                    model_name='all-MiniLM-L6-v2',
                    collection_name='docs',
                    vector_name='fast-all-minilm-l6-v2',
                    dimensions=384
                ),
                'mpnet': SearchConfig(
                    name='mpnet',
                    model_name='all-mpnet-base-v2',
                    collection_name='docs_mpnet',
                    vector_name='mpnet-base-v2',
                    dimensions=768
                ),
                'codebert': SearchConfig(
                    name='codebert',
                    model_name='microsoft/codebert-base',
                    collection_name='docs_codebert',
                    vector_name='codebert-base',
                    dimensions=768
                ),
                'minilm_l12': SearchConfig(
                    name='minilm_l12',
                    model_name='all-MiniLM-L12-v2',
                    collection_name='docs_minilm_l12',
                    vector_name='minilm-l12-v2',
                    dimensions=384
                )
            }
            self.save_configs(default_configs)
            return default_configs
        
        with open(self.config_path) as f:
            data = json.load(f)
            return {name: SearchConfig.from_dict(config) for name, config in data.items()}
    
    def save_configs(self, configs: Dict[str, SearchConfig]):
        """Save configurations to file.

        Serializes the current search configurations to JSON and writes them to
        the config file. Used to persist new or modified configurations.

        Args:
            configs: Dictionary mapping configuration names to SearchConfig objects

        Returns:
            None. Writes JSON to self.config_path with 2-space indentation.
        """
        data = {name: config.to_dict() for name, config in configs.items()}
        with open(self.config_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def list_available_configs(self):
        """List all available search configurations"""
        logger.info("Available Search Configurations:")
        logger.info("-" * 40)
        for name, config in self.configs.items():
            logger.info(f"• {name}")
            logger.info(f"  Model: {config.model_name}")
            logger.info(f"  Collection: {config.collection_name}")
            logger.info(f"  Dimensions: {config.dimensions}")
            
            # Check if collection exists
            try:
                info = self.client.get_collection(config.collection_name)
                logger.info(f"  Status: Ready ({info.points_count} documents)")
            except:
                logger.info(f"  Status: Collection not found")
            logger.info("")
    
    def get_model(self, config: SearchConfig) -> SentenceTransformer:
        """Get model instance (cached).

        Retrieves or loads the SentenceTransformer model specified in the config.
        Models are cached in memory after first load to avoid repeated downloads
        and initialization overhead.

        Args:
            config: SearchConfig object containing the model_name to load

        Returns:
            SentenceTransformer instance ready for encoding text to vectors.
            Cached instance is returned on subsequent calls for same config.

        Notes:
            - First access downloads model from HuggingFace if not cached locally
            - Subsequent accesses return the in-memory cached instance
            - Prints status message when loading a new model
        """
        if config.name not in self.loaded_models:
            logger.info(f"Loading model: {config.model_name}")
            self.loaded_models[config.name] = SentenceTransformer(config.model_name, trust_remote_code=True)
        return self.loaded_models[config.name]
    
    def search(self, query: str, config_name: str, limit: int = 10,
               score_threshold: float = 0.0, sort_by: str = "similarity",
               after_date: str = None, show_metadata: bool = False,
               split_terms: bool = False, operator: str = "AND",
               filters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Search using specified configuration"""
        
        # Handle multi-term search if requested
        if split_terms:
            return self._multi_term_search(query, config_name, limit, score_threshold, 
                                         sort_by, after_date, operator)
        
        if config_name not in self.configs:
            raise ValueError(f"Configuration '{config_name}' not found. Available: {list(self.configs.keys())}")
        
        config = self.configs[config_name]
        model = self.get_model(config)
        
        # Check if collection exists
        try:
            collection_info = self.client.get_collection(config.collection_name)
        except:
            raise ValueError(f"Collection '{config.collection_name}' does not exist. Run ingestion first.")
        
        # Encode query
        query_vector = model.encode(query).tolist()

        # Get more results for filtering/sorting if needed
        search_limit = max(limit * 3, 50) if sort_by != "similarity" else limit

        # Build Qdrant filter from filters dict
        qdrant_filter = None
        if filters:
            must_conditions = []
            for key, value in filters.items():
                must_conditions.append(
                    FieldCondition(
                        key=key,
                        match=MatchValue(value=value)
                    )
                )
            qdrant_filter = Filter(must=must_conditions)

        try:
            # Search using configured vector name
            search_result = self.client.query_points(
                collection_name=config.collection_name,
                query=query_vector,
                using=config.vector_name,
                query_filter=qdrant_filter,
                limit=search_limit,
                score_threshold=score_threshold,
                with_payload=True,
                with_vectors=False
            ).points
            
        except Exception as e:
            logger.error(f"Search error with {config.vector_name}: {e}")
            # Fallback to direct vector search
            try:
                search_result = self.client.query_points(
                    collection_name=config.collection_name,
                    query=query_vector,
                    limit=search_limit,
                    score_threshold=score_threshold,
                    with_payload=True,
                    with_vectors=False
                ).points
            except Exception as e2:
                logger.error(f"Fallback search also failed: {e2}")
                return []
        
        # Process results with metadata extraction
        results = []
        after_datetime = None
        if after_date:
            try:
                after_datetime = datetime.strptime(after_date, "%Y-%m-%d")
            except ValueError:
                logger.error(f"Invalid date format: {after_date}. Use YYYY-MM-DD")
                return []
        
        for hit in search_result:
            content = hit.payload.get('information', hit.payload.get('document', ''))
            extracted_metadata = self.extract_yaml_frontmatter(content)
            
            # Get timestamp
            timestamp_str = (
                extracted_metadata.get('timestamp') or 
                extracted_metadata.get('last_updated') or 
                extracted_metadata.get('created') or 
                extracted_metadata.get('date')
            )
            
            parsed_timestamp = self.parse_timestamp(timestamp_str) if timestamp_str else None
            
            # Apply date filter
            if after_datetime and parsed_timestamp and parsed_timestamp < after_datetime:
                continue
            
            result = {
                'id': hit.id,
                'score': float(hit.score),
                'content': content,
                'extracted_metadata': extracted_metadata,
                'timestamp': timestamp_str,
                'parsed_timestamp': parsed_timestamp,
                'config_used': config_name,
                'model_used': config.model_name
            }
            
            results.append(result)
        
        # Sort results
        if sort_by == "date" and results:
            results.sort(key=lambda x: (
                x['parsed_timestamp'] or datetime.min,
                x['score']
            ), reverse=True)
        elif sort_by == "hybrid" and results:
            # Hybrid scoring
            timestamps = [r['parsed_timestamp'] for r in results if r['parsed_timestamp']]
            if timestamps:
                min_time = min(timestamps)
                max_time = max(timestamps)
                time_range = (max_time - min_time).total_seconds()
                
                if time_range > 0:
                    for result in results:
                        if result['parsed_timestamp']:
                            recency_score = (result['parsed_timestamp'] - min_time).total_seconds() / time_range
                            result['hybrid_score'] = 0.6 * result['score'] + 0.4 * recency_score
                        else:
                            result['hybrid_score'] = result['score'] * 0.6
                    
                    results.sort(key=lambda x: x['hybrid_score'], reverse=True)
        
        return results[:limit]
    
    def extract_yaml_frontmatter(self, content: str) -> Dict[str, Any]:
        """Extract YAML frontmatter from document content"""
        metadata = {}
        
        yaml_pattern = r'^---\s*\n(.*?)\n---\s*\n'
        match = re.match(yaml_pattern, content, re.MULTILINE | re.DOTALL)
        
        if match:
            yaml_content = match.group(1)
            
            # Extract common timestamp fields
            timestamp_patterns = [
                (r'timestamp:\s*["\']?([^"\'\n]+)["\']?', 'timestamp'),
                (r'last_updated:\s*["\']?([^"\'\n]+)["\']?', 'last_updated'),
                (r'created:\s*["\']?([^"\'\n]+)["\']?', 'created'),
                (r'date:\s*["\']?([^"\'\n]+)["\']?', 'date'),
            ]
            
            for pattern, field in timestamp_patterns:
                match = re.search(pattern, yaml_content, re.IGNORECASE)
                if match:
                    metadata[field] = match.group(1)
            
            # Extract other metadata
            other_patterns = [
                (r'status:\s*["\']?([^"\'\n]+)["\']?', 'status'),
                (r'type:\s*["\']?([^"\'\n]+)["\']?', 'type'),
                (r'category:\s*["\']?([^"\'\n]+)["\']?', 'category'),
                (r'scope:\s*["\']?([^"\'\n]+)["\']?', 'scope'),
                (r'chu_keywords:\s*["\']?([^"\'\n]+)["\']?', 'chu_keywords'),
            ]
            
            for pattern, field in other_patterns:
                match = re.search(pattern, yaml_content, re.IGNORECASE)
                if match:
                    metadata[field] = match.group(1)
        
        return metadata
    
    def parse_timestamp(self, timestamp_str: str) -> Optional[datetime]:
        """Parse various timestamp formats to datetime"""
        if not timestamp_str:
            return None
            
        formats = [
            "%Y-%m-%dT%H:%M:%S-0800",
            "%Y-%m-%dT%H:%M:%S-0700",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(timestamp_str, fmt)
            except ValueError:
                continue
        
        return None
    
    def _multi_term_search(self, query: str, config_name: str, limit: int, 
                          score_threshold: float, sort_by: str, after_date: str, 
                          operator: str) -> List[Dict[str, Any]]:
        """
        Perform multi-term search by splitting query into individual terms
        and combining results using AND/OR logic
        """
        # Split query into terms (simple whitespace split)
        terms = query.strip().split()
        if len(terms) <= 1:
            # Fall back to regular search if only one term
            return self.search(query, config_name, limit, score_threshold, sort_by, 
                             after_date, show_metadata=False, split_terms=False, operator=operator)
        
        # Perform individual searches for each term
        term_results = {}
        all_results = {}
        
        for term in terms:
            results = self.search(term, config_name, limit * 2, score_threshold, sort_by, 
                                after_date, show_metadata=False, split_terms=False, operator=operator)
            term_results[term] = results
            
            # Collect all results by ID
            for result in results:
                result_id = result['id']
                if result_id not in all_results:
                    all_results[result_id] = result.copy()
                    all_results[result_id]['term_scores'] = {}
                    all_results[result_id]['matching_terms'] = []
                
                all_results[result_id]['term_scores'][term] = result['score']
                all_results[result_id]['matching_terms'].append(term)
        
        # Apply AND/OR logic
        filtered_results = []
        
        for result_id, result in all_results.items():
            matching_terms = result['matching_terms']
            
            if operator.upper() == "AND":
                # Document must contain all terms
                if len(matching_terms) == len(terms):
                    # Calculate combined score (average of term scores)
                    avg_score = sum(result['term_scores'].values()) / len(result['term_scores'])
                    result['score'] = avg_score
                    result['combined_score_method'] = 'average'
                    filtered_results.append(result)
            else:  # OR logic
                # Document must contain at least one term
                if len(matching_terms) >= 1:
                    # Calculate combined score (max of term scores)
                    max_score = max(result['term_scores'].values())
                    result['score'] = max_score
                    result['combined_score_method'] = 'maximum'
                    filtered_results.append(result)
        
        # Sort by combined score (descending)
        filtered_results.sort(key=lambda x: x['score'], reverse=True)
        
        # Apply the original sorting logic if requested
        if sort_by == "date" and filtered_results:
            filtered_results.sort(key=lambda x: (
                x['parsed_timestamp'] or datetime.min,
                x['score']
            ), reverse=True)
        elif sort_by == "hybrid" and filtered_results:
            # Apply hybrid scoring
            timestamps = [r['parsed_timestamp'] for r in filtered_results if r['parsed_timestamp']]
            if timestamps:
                min_time = min(timestamps)
                max_time = max(timestamps)
                time_range = (max_time - min_time).total_seconds()
                
                if time_range > 0:
                    for result in filtered_results:
                        if result['parsed_timestamp']:
                            recency_score = (result['parsed_timestamp'] - min_time).total_seconds() / time_range
                            result['hybrid_score'] = 0.6 * result['score'] + 0.4 * recency_score
                        else:
                            result['hybrid_score'] = result['score'] * 0.6
                    
                    filtered_results.sort(key=lambda x: x['hybrid_score'], reverse=True)
        
        return filtered_results[:limit]
    
    def compare_configs(self, query: str, config_names: List[str], limit: int = 5):
        """Compare search results across multiple configurations"""
        logger.info(f"Comparing search results for: '{query}'")
        logger.info("=" * 60)
        
        for config_name in config_names:
            if config_name not in self.configs:
                logger.error(f"Configuration '{config_name}' not found")
                continue
            
            try:
                results = self.search(query, config_name, limit=limit)
                config = self.configs[config_name]
                
                logger.info(f"\n{config_name.upper()} ({config.model_name}):")
                logger.info("-" * 50)
                
                if not results:
                    logger.info("  No results found")
                    continue
                
                for i, result in enumerate(results, 1):
                    preview = result['content'][:100].replace('\n', ' ') + "..."
                    logger.info(f"  {i}. Score: {result['score']:.4f}")
                    logger.info(f"     {preview}")
                
                avg_score = sum(r['score'] for r in results) / len(results)
                logger.info(f"  Average Score: {avg_score:.4f}")
                
            except Exception as e:
                logger.error(f"Error with {config_name}: {e}")

def main():
    parser = argparse.ArgumentParser(description='Modular Qdrant Search')
    parser.add_argument('query', nargs='?', help='Search query')
    parser.add_argument('--config', '-c', default='e5_large', help='Configuration to use')
    parser.add_argument('--list-configs', action='store_true', help='List available configurations')
    parser.add_argument('--compare', nargs='+', help='Compare multiple configurations')
    parser.add_argument('--limit', type=int, default=10, help='Number of results')
    parser.add_argument('--threshold', type=float, default=0.0, help='Score threshold')
    parser.add_argument('--sort-by', choices=['similarity', 'date', 'hybrid'], default='similarity')
    parser.add_argument('--after', help='Only show documents after date (YYYY-MM-DD)')
    parser.add_argument('--show-metadata', action='store_true', help='Show extracted metadata')
    parser.add_argument('--split-terms', action='store_true', help='Split query into individual terms for multi-term search')
    parser.add_argument('--operator', choices=['AND', 'OR'], default='AND', 
                       help='Operator for combining multiple terms (default: AND)')
    
    args = parser.parse_args()
    
    searcher = ModularSearch()
    
    if args.list_configs:
        searcher.list_available_configs()
        return
    
    if args.compare:
        if not args.query:
            logger.error("Query required for comparison")
            return
        searcher.compare_configs(args.query, args.compare, args.limit)
        return
    
    if not args.query:
        logger.error("Please provide a search query or use --list-configs")
        parser.print_help()
        return
    
    # Perform search
    try:
        results = searcher.search(
            args.query, 
            args.config,
            limit=args.limit,
            score_threshold=args.threshold,
            sort_by=args.sort_by,
            after_date=args.after,
            show_metadata=args.show_metadata,
            split_terms=args.split_terms,
            operator=args.operator
        )
        
        config = searcher.configs[args.config]
        logger.info(f"Search: '{args.query}' using {args.config} ({config.model_name})")
        if args.split_terms:
            logger.info(f"Multi-term search: {args.operator} operator")
        logger.info(f"Found {len(results)} results")
        logger.info("-" * 60)
        
        for i, result in enumerate(results, 1):
            logger.info(f"\nResult {i} (Score: {result['score']:.4f}):")
            logger.info(f"ID: {result['id']}")
            logger.info(f"Config: {result['config_used']} | Model: {result['model_used']}")
            
            if result['timestamp']:
                logger.info(f"Timestamp: {result['timestamp']}")
            
            if args.show_metadata and result['extracted_metadata']:
                logger.info(f"Metadata: {result['extracted_metadata']}")
            
            if args.sort_by == "hybrid" and 'hybrid_score' in result:
                logger.info(f"Hybrid Score: {result['hybrid_score']:.4f}")
            
            # Show multi-term search info if applicable
            if 'matching_terms' in result:
                logger.info(f"Matching terms: {', '.join(result['matching_terms'])}")
                if 'combined_score_method' in result:
                    logger.info(f"Score method: {result['combined_score_method']}")
            
            content_preview = result['content'][:200] + "..." if len(result['content']) > 200 else result['content']
            logger.info(f"Content: {content_preview}")
            logger.info("-" * 80)
            
    except Exception as e:
        logger.error(f"Error: {e}")

if __name__ == "__main__":
    main()