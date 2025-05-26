import re
from typing import Dict, List, Any, Tuple, Union, Optional
from difflib import SequenceMatcher

def normalize_text(text: str) -> str:
    """Normalize text for more accurate comparison."""
    text = text.lower().strip()
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text)
    # Normalize common punctuation
    text = re.sub(r'[.,;:!?]', '', text)
    return text


def parse_markdown_table(markdown_text: str) -> List[List[str]]:
    """Parse markdown table into a 2D array of cell contents."""
    # Clean the input to handle potential variations
    lines = [line.strip() for line in markdown_text.strip().split('\n')]
    
    # Filter out empty lines and non-table lines
    table_lines = [line for line in lines if line and line.startswith('|')]
    
    # Remove header separator row if present
    rows = []
    for i, line in enumerate(table_lines):
        # Skip separator lines (contain only |, -, and :)
        if i > 0 and re.match(r'^[\|\-:\s]+$', line):
            continue
        
        # Extract cell content
        cells = line.split('|')
        # Remove empty first/last cells from pipe at beginning/end of line
        if not cells[0].strip():
            cells = cells[1:]
        if not cells[-1].strip():
            cells = cells[:-1]
            
        # Clean whitespace
        cells = [cell.strip() for cell in cells]
        rows.append(cells)
    
    return rows

def evaluate_table_content(actual_table: List[List[str]], expected_table: List[List[str]]) -> Tuple[float, str]:
    """Evaluate whether all expected content is present in the table."""
    expected_cells = [cell for row in expected_table for cell in row]
    actual_cells = [cell for row in actual_table for cell in row]
    
    found_cells = 0
    missing_cells = []
    
    for expected_cell in expected_cells:
        if any(normalize_text(expected_cell) == normalize_text(actual_cell) for actual_cell in actual_cells):
            found_cells += 1
        else:
            # Check for partial matches
            best_match = None
            best_ratio = 0
            for actual_cell in actual_cells:
                ratio = SequenceMatcher(None, normalize_text(expected_cell), normalize_text(actual_cell)).ratio()
                if ratio > 0.8 and ratio > best_ratio:  # 80% similarity threshold
                    best_match = actual_cell
                    best_ratio = ratio
            
            if best_match:
                found_cells += best_ratio
            else:
                missing_cells.append(expected_cell)
    
    score = found_cells / len(expected_cells) if expected_cells else 1.0
    
    if missing_cells:
        reason = f"Missing content: {', '.join(missing_cells[:5])}"
        if len(missing_cells) > 5:
            reason += f" and {len(missing_cells) - 5} more"
    else:
        reason = "All expected content found"
    
    return score, reason

def evaluate_table_structure(actual_table: List[List[str]], expected_table: List[List[str]]) -> Tuple[float, str]:
    """Evaluate table structure (rows and columns)."""
    expected_rows = len(expected_table)
    expected_cols = max(len(row) for row in expected_table) if expected_table else 0
    
    actual_rows = len(actual_table)
    actual_cols = max(len(row) for row in actual_table) if actual_table else 0
    
    row_score = min(actual_rows / expected_rows, 1.0) if expected_rows else 0
    col_score = min(actual_cols / expected_cols, 1.0) if expected_cols else 0
    
    structure_score = (row_score + col_score) / 2
    
    reason = f"Row match: {actual_rows}/{expected_rows}, Column match: {actual_cols}/{expected_cols}"
    
    return structure_score, reason

def evaluate_cell_positions(actual_table: List[List[str]], expected_table: List[List[str]]) -> Tuple[float, str]:
    """Evaluate if cells are in the correct positions using a neighbor-based approach with fuzzy matching."""
    total_cells = 0
    correct_positions = 0
    misplaced_cells = []

    # Create cell coordinates mapping for expected table
    expected_cell_coords = {}
    for i, row in enumerate(expected_table):
        for j, cell in enumerate(row):
            if cell.strip():  # Skip empty cells
                expected_cell_coords[normalize_text(cell)] = (i, j)

    # Check cell relationships in actual table
    for i, row in enumerate(actual_table):
        for j, cell in enumerate(row):
            norm_cell = normalize_text(cell)
            if not norm_cell or norm_cell not in expected_cell_coords:
                continue

            total_cells += 1
            expected_i, expected_j = expected_cell_coords[norm_cell]

            # Get neighbors for validation
            actual_neighbors = get_neighbors(actual_table, i, j)
            expected_neighbors = get_neighbors(expected_table, expected_i, expected_j)

            # Fuzzy match both neighbors (at least two fuzzy matches required)
            matches = 0
            for a_neighbor in actual_neighbors:
                for e_neighbor in expected_neighbors:
                    ratio = SequenceMatcher(None, normalize_text(a_neighbor), normalize_text(e_neighbor)).ratio()
                    if ratio > 0.8:
                        matches += 1
                        break  # Only count one match per actual neighbor

            if matches >= min(2, len(expected_neighbors)):  # Require both neighbors to match if 2 exist
                correct_positions += 1
            else:
                misplaced_cells.append(cell)

    score = correct_positions / total_cells if total_cells else 1.0

    if misplaced_cells:
        reason = f"Misplaced cells: {', '.join(misplaced_cells[:5])}"
        if len(misplaced_cells) > 5:
            reason += f" and {len(misplaced_cells) - 5} more"
    else:
        reason = "All cells correctly positioned"

    return score, reason

def get_neighbors(table: List[List[str]], row: int, col: int) -> List[str]:
    """Get the neighboring cells for a given cell."""
    neighbors = []
    
    # Check bounds and add valid neighbors
    directions = [(-1, 0), (0, -1)]  # Up,  left
    
    for dr, dc in directions:
        new_row, new_col = row + dr, col + dc
        if 0 <= new_row < len(table) and 0 <= new_col < len(table[new_row]):
            neighbor = table[new_row][new_col].strip()
            if neighbor:
                neighbors.append(normalize_text(neighbor))
    
    return neighbors

def get_assert(output: str, context) -> Union[Dict[str, Any], bool, float]:
    """Main assertion function for table evaluation."""
    expected_content = context["vars"]["expected_content"]
    
    # Parse tables
    try:
        actual_table = parse_markdown_table(output)
        expected_table = parse_markdown_table(expected_content)
    except Exception as e:
        return {
            'pass': False,  
            'score': 0.0,
            'reason': f"Failed to parse tables: {str(e)}"
        }
    
    # Skip empty tables
    if not actual_table or not expected_table:
        return {
            'pass': False,  
            'score': 0.0,
            'reason': "Empty table detected"
        }
    
    # Evaluate content presence
    content_score, content_reason = evaluate_table_content(actual_table, expected_table)
    
    # Evaluate structure
    structure_score, structure_reason = evaluate_table_structure(actual_table, expected_table)
    
    # Evaluate cell positions
    position_score, position_reason = evaluate_cell_positions(actual_table, expected_table)
    
    # Calculate overall score
    overall_score = (content_score * 0.4 + structure_score * 0.2 + position_score * 0.4)
    overall_pass = overall_score >= 0.8  # 80% threshold for passing
    
    # Create component results
    component_results = [
        {
            'pass': content_score >= 0.8, 
            'score': content_score,
            'reason': content_reason
        },
        {
            'pass': structure_score >= 0.8,  
            'score': structure_score,
            'reason': structure_reason
        },
        {
            'pass': position_score >= 0.8, 
            'score': position_score,
            'reason': position_reason
        }
    ]
    
    # Overall summary
    overall_reason = f"Content: {content_score:.2f}, Structure: {structure_score:.2f}, Positioning: {position_score:.2f}"
    
    return {
        'pass': overall_pass,
        'score': overall_score,
        'reason': overall_reason,
        'componentResults': component_results,  
        'namedScores': {  
            'ContentPresence': content_score,
            'StructureCorrectness': structure_score,
            'CellPositionAccuracy': position_score,
            'TableMatchScore': overall_score
        }
    }