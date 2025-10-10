# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

"""
Test script to verify SessionEntity is correctly constructed from Jaeger format data.
This script validates that all session properties are properly extracted and populated.
"""

import json
from pathlib import Path
from typing import Dict, Any

from metrics_computation_engine.entities.core.trace_processor import TraceProcessor
from metrics_computation_engine.logger import setup_logger

# --- Configuration ---
RAW_TRACES_PATH: Path = Path(__file__).parent / "data" / "8efde096af0e9d89e59b19905e487fa6.json"

logger = setup_logger(name=__name__)


def print_section(title: str):
    """Print a formatted section header"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80 + "\n")


def verify_session_entity():
    """Main verification function for SessionEntity from Jaeger data"""
    
    print_section("JAEGER FORMAT - SESSION ENTITY VERIFICATION")
    
    # Load Jaeger format data
    logger.info(f"Loading Jaeger format traces from: {RAW_TRACES_PATH}")
    raw_spans = json.loads(RAW_TRACES_PATH.read_text())
    logger.info(f"✓ Loaded {len(raw_spans)} raw spans")
    
    # Process traces to create sessions
    trace_processor = TraceProcessor()
    sessions_set = trace_processor.process_raw_traces(raw_spans)
    
    logger.info(f"✓ Processed into {len(sessions_set.sessions)} session(s)")
    
    if not sessions_set.sessions:
        logger.error("❌ NO SESSIONS CREATED - Test Failed!")
        return
    
    # Get the first (and likely only) session
    session = sessions_set.sessions[0]
    
    # --- VERIFICATION TESTS ---
    
    print_section("1. CORE SESSION PROPERTIES")
    
    tests_passed = 0
    tests_failed = 0
    
    # Test 1: Session ID
    print(f"session_id: {session.session_id}")
    if session.session_id:
        print("  ✓ PASS: Session ID is populated")
        tests_passed += 1
    else:
        print("  ❌ FAIL: Session ID is missing")
        tests_failed += 1
    
    # Test 2: App Name
    print(f"\napp_name: {session.app_name}")
    if session.app_name and session.app_name != "unknown":
        print("  ✓ PASS: App name is populated")
        tests_passed += 1
    else:
        print("  ❌ FAIL: App name is missing or 'unknown'")
        tests_failed += 1
    
    # Test 3: Start/End Time
    print(f"\nstart_time: {session.start_time}")
    print(f"end_time: {session.end_time}")
    if session.start_time and session.end_time:
        print("  ✓ PASS: Timestamps are populated")
        tests_passed += 1
    else:
        print("  ❌ FAIL: Timestamps are missing")
        tests_failed += 1
    
    # Test 4: Duration
    print(f"\nduration: {session.duration}")
    if session.duration > 0:
        print("  ✓ PASS: Duration is positive")
        tests_passed += 1
    else:
        print("  ❌ FAIL: Duration is zero or negative")
        tests_failed += 1
    
    # Test 5: Spans
    print(f"\ntotal spans: {len(session.spans)}")
    if len(session.spans) > 0:
        print("  ✓ PASS: Spans are present")
        tests_passed += 1
    else:
        print("  ❌ FAIL: No spans found")
        tests_failed += 1
    
    print_section("2. SPAN CATEGORIZATION")
    
    # Test 6: LLM Spans
    print(f"llm_spans: {len(session.llm_spans)}")
    if len(session.llm_spans) > 0:
        print("  ✓ PASS: LLM spans detected")
        tests_passed += 1
        # Show sample LLM span
        llm_span = session.llm_spans[0]
        print(f"  Sample LLM span:")
        print(f"    - span_id: {llm_span.span_id}")
        print(f"    - entity_type: {llm_span.entity_type}")
        print(f"    - entity_name: {llm_span.entity_name}")
    else:
        print("  ⚠️  WARNING: No LLM spans detected")
        tests_failed += 1
    
    # Test 7: Agent Spans
    print(f"\nagent_spans: {len(session.agent_spans)}")
    if len(session.agent_spans) > 0:
        print("  ✓ PASS: Agent spans detected")
        tests_passed += 1
        # Show sample agent span
        agent_span = session.agent_spans[0]
        print(f"  Sample Agent span:")
        print(f"    - span_id: {agent_span.span_id}")
        print(f"    - entity_type: {agent_span.entity_type}")
        print(f"    - entity_name: '{agent_span.entity_name}'")
        print(f"    - span_name: {agent_span.span_name}")
    else:
        print("  ⚠️  WARNING: No agent spans detected")
        tests_failed += 1
    
    # Test 8: Tool Spans
    print(f"\ntool_spans: {len(session.tool_spans)}")
    if len(session.tool_spans) > 0:
        print("  ✓ PASS: Tool spans detected")
        tests_passed += 1
    else:
        print("  ⚠️  INFO: No tool spans (this may be expected)")
    
    print_section("3. CONVERSATION DATA")
    
    # Test 9: Input Query
    print(f"input_query: {session.input_query[:100] if session.input_query else None}...")
    if session.input_query:
        print("  ✓ PASS: Input query is populated")
        tests_passed += 1
    else:
        print("  ❌ FAIL: Input query is missing")
        tests_failed += 1
    
    # Test 10: Final Response
    print(f"\nfinal_response: {session.final_response[:100] if session.final_response else None}...")
    if session.final_response:
        print("  ✓ PASS: Final response is populated")
        tests_passed += 1
    else:
        print("  ❌ FAIL: Final response is missing")
        tests_failed += 1
    
    # Test 11: Conversation Data
    print(f"\nconversation_data: {session.conversation_data is not None}")
    if session.conversation_data:
        print("  ✓ PASS: Conversation data structure exists")
        tests_passed += 1
        print(f"  Conversation turns: {len(session.conversation_data.get('turns', []))}")
    else:
        print("  ⚠️  WARNING: Conversation data is None")
    
    print_section("4. WORKFLOW & EXECUTION DATA")
    
    # Test 12: Workflow Data
    print(f"workflow_data: {session.workflow_data is not None}")
    if session.workflow_data:
        print("  ✓ INFO: Workflow data exists")
        if isinstance(session.workflow_data, dict):
            print(f"  Keys: {list(session.workflow_data.keys())}")
    else:
        print("  ℹ️  INFO: No workflow data (may be expected for Jaeger format)")
    
    # Test 13: Execution Tree
    print(f"\nexecution_tree: {session.execution_tree is not None}")
    if session.execution_tree:
        print("  ✓ INFO: Execution tree exists")
    else:
        print("  ℹ️  INFO: No execution tree (may be expected for Jaeger format)")
    
    print_section("5. ENTITY NAME EXTRACTION (CRITICAL)")
    
    # Test 14: Agent Entity Names
    print("Agent Entity Names:")
    agent_entity_names = [span.entity_name for span in session.agent_spans]
    print(f"  Raw list: {agent_entity_names}")
    
    non_empty_names = [name for name in agent_entity_names if name and name != "unknown"]
    print(f"  Non-empty/non-unknown names: {non_empty_names}")
    
    if len(non_empty_names) > 0:
        print(f"  ✓ PASS: {len(non_empty_names)} valid agent entity names found")
        tests_passed += 1
    else:
        print(f"  ❌ FAIL: No valid agent entity names (all are empty or 'unknown')")
        print(f"  This means GoalSuccessRate.entities_involved will be empty!")
        tests_failed += 1
        
        # Debug: Check what attributes are available
        if session.agent_spans:
            print("\n  Debug - First agent span attributes:")
            first_agent = session.agent_spans[0]
            if first_agent.attrs:
                name_keys = [k for k in first_agent.attrs.keys() if 'name' in k.lower() or 'entity' in k.lower()]
                print(f"    Relevant attribute keys: {name_keys[:10]}")
                for key in name_keys[:5]:
                    print(f"      {key}: {first_agent.attrs.get(key)}")
    
    # Test 15: LLM Entity Names
    print("\nLLM Entity Names:")
    llm_entity_names = [span.entity_name for span in session.llm_spans]
    unique_llm_names = list(set(llm_entity_names))
    print(f"  Unique LLM entities: {unique_llm_names}")
    
    if len(unique_llm_names) > 0 and unique_llm_names[0] != "unknown":
        print(f"  ✓ PASS: LLM entity names properly extracted")
        tests_passed += 1
    else:
        print(f"  ⚠️  WARNING: LLM entity names are 'unknown' or missing")
    
    print_section("6. AGENT STATISTICS")
    
    # Test 16: Agent Stats
    print(f"agent_stats: {session.agent_stats is not None}")
    if session.agent_stats:
        print("  ✓ INFO: Agent statistics exist")
        if isinstance(session.agent_stats, dict):
            print(f"  Stats keys: {list(session.agent_stats.keys())}")
    else:
        print("  ℹ️  INFO: No agent stats (may be expected)")
    
    print_section("TEST SUMMARY")
    
    total_tests = tests_passed + tests_failed
    pass_rate = (tests_passed / total_tests * 100) if total_tests > 0 else 0
    
    print(f"Total Tests: {total_tests}")
    print(f"✓ Passed: {tests_passed}")
    print(f"❌ Failed: {tests_failed}")
    print(f"Pass Rate: {pass_rate:.1f}%")
    print()
    
    if tests_failed == 0:
        print("🎉 ALL CRITICAL TESTS PASSED!")
        print("SessionEntity is correctly constructed from Jaeger format data.")
    elif tests_failed <= 2:
        print("⚠️  MOSTLY PASSING - Some non-critical tests failed")
        print("SessionEntity is functional but may have minor issues.")
    else:
        print("❌ MULTIPLE TESTS FAILED")
        print("SessionEntity may not be properly constructed from Jaeger format data.")
    
    print("\n" + "=" * 80 + "\n")
    
    return {
        "total_tests": total_tests,
        "tests_passed": tests_passed,
        "tests_failed": tests_failed,
        "pass_rate": pass_rate,
        "session_id": session.session_id,
        "app_name": session.app_name,
        "total_spans": len(session.spans),
        "llm_spans": len(session.llm_spans),
        "agent_spans": len(session.agent_spans),
        "tool_spans": len(session.tool_spans),
        "has_input_query": bool(session.input_query),
        "has_final_response": bool(session.final_response),
        "agent_entity_names": agent_entity_names,
        "llm_entity_names": unique_llm_names,
    }


if __name__ == "__main__":
    try:
        result = verify_session_entity()
        
        # Save results to JSON for later analysis
        output_file = Path(__file__).parent / "jaeger_session_entity_verification.json"
        with open(output_file, "w") as f:
            json.dump(result, f, indent=2)
        
        print(f"Results saved to: {output_file}")
        
    except Exception as e:
        logger.error(f"Test failed with exception: {e}", exc_info=True)
        raise

