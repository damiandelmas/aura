#!/usr/bin/env python3
"""
Enhanced Qdrant Search with Timestamp Support
Extracts timestamps from YAML frontmatter and enables chronological sorting
"""

import sys
import argparse
import re
import logging
import warnings
from datetime import datetime
from typing import List, Dict, Any, Optional

# Suppress Pydantic warnings before imports
warnings.filterwarnings('ignore', category=UserWarning, module='pydantic')

from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer

from .config import config

logger = logging.getLogger(__name__)

class EnhancedQdrantSearch:
    def __init__(self, host: str = "localhost", port: int = config.qdrant_port, collection_name: str = "docs_e5_large"):
        """Initialize enhanced Qdrant connection with metadata parsing"""
        self.client = QdrantClient(host=host, port=port)
        self.collection_name = collection_name
        self.encoder = SentenceTransformer('intfloat/e5-large-v2')
        self.vector_name = "e5-large-v2"  # Named vector for E5-Large-v2
        
    def extract_yaml_frontmatter(self, content: str) -> Dict[str, Any]:
        """Extract YAML frontmatter from document content"""
        metadata = {}
        
        # Match YAML frontmatter pattern
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
            
        # Common timestamp formats
        formats = [
            "%Y-%m-%dT%H:%M:%S-0800",  # 2025-07-23T03:33:00-0800
            "%Y-%m-%dT%H:%M:%S-0700",  # 2025-07-16T23:26:00-0700
            "%Y-%m-%dT%H:%M:%SZ",      # 2025-06-26T20:52:00Z
            "%Y-%m-%dT%H:%M",          # 2025-06-14T05:05
            "%Y-%m-%d %H:%M:%S",       # 2025-07-24 16:05:00
            "%Y-%m-%d",                # 2025-07-24
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(timestamp_str, fmt)
            except ValueError:
                continue
        
        return None
    
    def search(self, query: str, limit: int = 10, score_threshold: float = 0.0,
               sort_by: str = "similarity", after_date: str = None,
               split_terms: bool = False, operator: str = "AND",
               filters: Dict[str, str] = None) -> List[Dict[str, Any]]:
        """
        Enhanced search with metadata extraction and sorting options

        Args:
            query: Search text or multiple queries separated by space when split_terms=True
            limit: Maximum number of results
            score_threshold: Minimum similarity score
            sort_by: "similarity" (default), "date", or "hybrid"
            after_date: Only return documents after this date (YYYY-MM-DD format)
            split_terms: If True, split query into individual terms for multi-term search
            operator: "AND" or "OR" operator for combining multiple terms (when split_terms=True)
            filters: Metadata filters (e.g., {'phase': 'develop', 'section_type': 'Decisions'})
        """
        # Handle multi-term search if requested
        if split_terms:
            return self._multi_term_search(query, limit, score_threshold, sort_by, after_date, operator, filters)

        # Encode query to vector
        query_vector = self.encoder.encode(query).tolist()

        # Get more results for filtering/sorting
        search_limit = max(limit * 3, 50) if sort_by != "similarity" else limit

        # Build Qdrant filter if provided
        from qdrant_client.models import Filter, FieldCondition, MatchValue
        query_filter = None
        if filters:
            must_conditions = []
            for key, value in filters.items():
                must_conditions.append(
                    FieldCondition(key=key, match=MatchValue(value=value))
                )
            query_filter = Filter(must=must_conditions)

        try:
            # Search using named vector for E5-Large-v2
            search_result = self.client.query_points(
                collection_name=self.collection_name,
                query=query_vector,
                using=self.vector_name,
                query_filter=query_filter,
                limit=search_limit,
                score_threshold=score_threshold,
                with_payload=True,
                with_vectors=False
            ).points
            
        except Exception as e:
            logger.error(f"Search error: {e}")
            
            # Fallback: try direct vector format
            try:
                search_result = self.client.query_points(
                    collection_name=self.collection_name,
                    query=query_vector,
                    limit=search_limit,
                    score_threshold=score_threshold,
                    with_payload=True,
                    with_vectors=False
                ).points
            except Exception as e2:
                logger.error(f"Fallback search also failed: {e2}")
                return []
        
        # Process results and extract metadata
        results = []
        after_datetime = None
        if after_date:
            try:
                after_datetime = datetime.strptime(after_date, "%Y-%m-%d")
            except ValueError:
                logger.error(f"Invalid date format: {after_date}. Use YYYY-MM-DD")
                return []
        
        for hit in search_result:
            content = hit.payload.get('content', hit.payload.get('information', hit.payload.get('document', '')))
            extracted_metadata = self.extract_yaml_frontmatter(content)
            
            # Get the most relevant timestamp
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
                'file_path': hit.payload.get('file_path', ''),
                'extracted_metadata': extracted_metadata,
                'timestamp': timestamp_str,
                'parsed_timestamp': parsed_timestamp,
                'original_metadata': hit.payload,  # Return full payload for rich metadata access
            }
            
            results.append(result)
        
        # Sort results based on sort_by parameter
        if sort_by == "date" and results:
            # Sort by timestamp (most recent first), then by similarity
            results.sort(key=lambda x: (
                x['parsed_timestamp'] or datetime.min,
                x['score']
            ), reverse=True)
        elif sort_by == "hybrid" and results:
            # Hybrid scoring: combine recency and similarity
            # Normalize timestamps to 0-1 scale
            timestamps = [r['parsed_timestamp'] for r in results if r['parsed_timestamp']]
            if timestamps:
                min_time = min(timestamps)
                max_time = max(timestamps)
                time_range = (max_time - min_time).total_seconds()
                
                if time_range > 0:
                    for result in results:
                        if result['parsed_timestamp']:
                            # Recency score (0-1, higher = more recent)
                            recency_score = (result['parsed_timestamp'] - min_time).total_seconds() / time_range
                            # Combine similarity (0-1) with recency (0-1)
                            result['hybrid_score'] = 0.6 * result['score'] + 0.4 * recency_score
                        else:
                            result['hybrid_score'] = result['score'] * 0.6  # Penalize missing timestamps
                    
                    results.sort(key=lambda x: x['hybrid_score'], reverse=True)
        
        # Return limited results
        return results[:limit]
    
    def _multi_term_search(self, query: str, limit: int, score_threshold: float,
                          sort_by: str, after_date: str, operator: str,
                          filters: Dict[str, str] = None) -> List[Dict[str, Any]]:
        """
        Perform multi-term search by splitting query into individual terms
        and combining results using AND/OR logic
        """
        # Split query into terms (simple whitespace split)
        terms = query.strip().split()
        if len(terms) <= 1:
            # Fall back to regular search if only one term
            return self.search(query, limit, score_threshold, sort_by, after_date,
                             split_terms=False, operator=operator, filters=filters)

        # Perform individual searches for each term
        term_results = {}
        all_results = {}

        for term in terms:
            results = self.search(term, limit * 2, score_threshold, sort_by, after_date,
                                split_terms=False, operator=operator, filters=filters)
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


def main():
    parser = argparse.ArgumentParser(description='Enhanced Qdrant Search with Timestamps')
    parser.add_argument('query', nargs='?', help='Search query')
    parser.add_argument('--limit', type=int, default=10, help='Number of results (default: 10)')
    parser.add_argument('--threshold', type=float, default=0.0, help='Score threshold (default: 0.0)')
    parser.add_argument('--sort-by', choices=['similarity', 'date', 'hybrid'], default='similarity',
                       help='Sort method: similarity (default), date, or hybrid')
    parser.add_argument('--after', help='Only show documents after date (YYYY-MM-DD)')
    parser.add_argument('--collection', default='docs_e5_large', help='Collection name (default: docs_e5_large)')
    parser.add_argument('--show-metadata', action='store_true', help='Show extracted metadata')
    parser.add_argument('--split-terms', action='store_true', help='Split query into individual terms for multi-term search')
    parser.add_argument('--operator', choices=['AND', 'OR'], default='AND', 
                       help='Operator for combining multiple terms (default: AND)')
    
    args = parser.parse_args()
    
    if not args.query:
        logger.error("Please provide a search query")
        parser.print_help()
        return
    
    # Initialize enhanced searcher  
    searcher = EnhancedQdrantSearch(collection_name=args.collection)
    
    # Perform search
    logger.info(f"Searching for: '{args.query}'")
    logger.info(f"Sort by: {args.sort_by}, Limit: {args.limit}, Threshold: {args.threshold}")
    if args.split_terms:
        logger.info(f"Multi-term search: {args.operator} operator")
    if args.after:
        logger.info(f"After date: {args.after}")
    logger.info("-" * 50)
    
    results = searcher.search(
        args.query, 
        limit=args.limit, 
        score_threshold=args.threshold,
        sort_by=args.sort_by,
        after_date=args.after,
        split_terms=args.split_terms,
        operator=args.operator
    )
    
    if not results:
        logger.info("No results found.")
        return
    
    for i, result in enumerate(results, 1):
        logger.info(f"\nResult {i} (Score: {result['score']:.4f}):")
        logger.info(f"ID: {result['id']}")
        
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
        
        # Show first 200 chars of content
        content_preview = result['content']  # Show full content as per working documentation
        logger.info(f"Content: {content_preview}")
        logger.info("-" * 80)


if __name__ == "__main__":
    main()