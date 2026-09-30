"""rftinterp - RFT pressure-depth interpretation with fixed fluid gradients."""
from .interpret import (GroupConfig, InterpretationResult, Line, classify_fluids,
                        contact_depth, find_lines, free_fit_contact, interpret_group,
                        optimize_cluster, projected_intercepts, segment_depth)
from .io import load_data, load_groups

__version__ = "0.1.0"
__all__ = ["GroupConfig", "InterpretationResult", "Line", "classify_fluids",
           "contact_depth", "find_lines", "free_fit_contact", "interpret_group",
           "optimize_cluster", "projected_intercepts", "segment_depth",
           "load_data", "load_groups"]
