#!/usr/bin/env python3
# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0
"""
Script to populate annotation database with sample data
Uses the annotation API endpoints to create test dataset
"""

import json
import random
import requests
import sys
from typing import List, Dict, Any

# Configuration
API_BASE_URL = "http://localhost:8080"
HEADERS = {"Content-Type": "application/json"}


class AnnotationDataPopulator:
    def __init__(self, api_base_url: str = API_BASE_URL):
        self.api_base_url = api_base_url
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

        # Store IDs for created resources
        self.session_success_type_id = None
        self.session_genre_type_id = None
        self.hallucination_type_id = None
        self.annotation_group_id = None
        self.llm_annotation_group_id = None
        self.group_item_ids = {}  # session_id -> group_item_id mapping
        self.llm_group_item_ids = {}  # session_id -> group_item_id mapping

        # Dataset IDs
        self.dataset_ds1_id = None
        self.dataset_ds2_id = None
        self.dataset_ds20_id = None

    def log_info(self, message: str):
        print(f"[INFO] {message}")

    def log_error(self, message: str):
        print(f"[ERROR] {message}")

    def log_success(self, message: str):
        print(f"[SUCCESS] ✓ {message}")

    def api_call(
        self,
        method: str,
        endpoint: str,
        data: Dict[Any, Any] = None,
        description: str = "",
    ) -> Dict[Any, Any]:
        """Make API call with error handling"""
        url = f"{self.api_base_url}{endpoint}"
        self.log_info(f"Making {method} request to {endpoint} - {description}")

        try:
            if method.upper() == "GET":
                response = self.session.get(url)
            elif method.upper() == "POST":
                response = self.session.post(url, json=data)
            elif method.upper() == "PUT":
                response = self.session.put(url, json=data)
            elif method.upper() == "DELETE":
                response = self.session.delete(url)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            if response.status_code >= 200 and response.status_code < 300:
                self.log_success(f"{description} (HTTP {response.status_code})")

                # Extract ID from Location header for POST requests
                result = {}
                try:
                    response_data = response.json()
                    result = response_data
                except json.JSONDecodeError:
                    result = {"status": "success"}

                if method.upper() == "POST" and "Location" in response.headers:
                    location = response.headers["Location"]
                    # Extract ID from location header (e.g., "/annotation-types/uuid" -> "uuid")
                    resource_id = location.split("/")[-1]
                    result["id"] = resource_id
                    self.log_info(f"Created resource with ID: {resource_id}")

                return result
            else:
                self.log_error(
                    f"Failed {description} (HTTP {response.status_code}): {response.text}"
                )
                return None

        except requests.exceptions.RequestException as e:
            self.log_error(f"Request failed for {description}: {str(e)}")
            return None

    def create_annotation_types(self):
        """Create the annotation types"""
        self.log_info("=== Creating Annotation Types ===")

        # Session Success (Boolean)
        session_success_type = {
            "name": "Session Success",
            "type": "boolean",
            "comment": "Boolean annotation for session outcomes",
        }

        success_result = self.api_call(
            "POST",
            "/annotation-types",
            session_success_type,
            "Session Success annotation type",
        )

        # Session Genre (Categorical)
        session_genre_type = {
            "name": "Session Genre",
            "type": "categorical",
            "categorical_list": [
                "product_info",
                "credit_card",
                "refund",
                "account",
                "other",
            ],
            "comment": "Categorical annotation with 5 categories",
        }

        genre_result = self.api_call(
            "POST",
            "/annotation-types",
            session_genre_type,
            "Session Genre annotation type",
        )

        # LLM Hallucination (Boolean)
        hallucination_type = {
            "name": "LLM Hallucination",
            "type": "boolean",
            "comment": "Boolean annotation for LLM hallucination detection",
        }

        hallucination_result = self.api_call(
            "POST",
            "/annotation-types",
            hallucination_type,
            "LLM Hallucination annotation type",
        )

        # Store the IDs for later use
        self.session_success_type_id = success_result["id"] if success_result else None
        self.session_genre_type_id = genre_result["id"] if genre_result else None
        self.hallucination_type_id = (
            hallucination_result["id"] if hallucination_result else None
        )

        return success_result and genre_result and hallucination_result

    def create_annotation_group(self):
        """Create the test annotation group"""
        self.log_info("=== Creating Annotation Group ===")

        annotation_group = {
            "name": "Test Annotation Group",
            "comment": "Sample annotation group for testing",
            "annotation_type_ids": [
                self.session_success_type_id,
                self.session_genre_type_id,
            ],
            "min_reviews": 2,
            "max_reviews": 4,
        }

        result = self.api_call(
            "POST", "/annotation-groups", annotation_group, "Test annotation group"
        )

        # Store the group ID for later use
        self.annotation_group_id = result["id"] if result else None

        return result

    def create_llm_annotation_group(self):
        """Create the LLM hallucination annotation group"""
        self.log_info("=== Creating LLM Annotation Group ===")

        llm_annotation_group = {
            "name": "test_group_llm",
            "comment": "LLM hallucination annotation group",
            "annotation_type_ids": [self.hallucination_type_id],
            "min_reviews": 2,
            "max_reviews": 4,
        }

        result = self.api_call(
            "POST", "/annotation-groups", llm_annotation_group, "LLM annotation group"
        )

        # Store the group ID for later use
        self.llm_annotation_group_id = result["id"] if result else None

        return result

    def generate_session_ids(self, count: int) -> List[str]:
        """Generate session IDs"""
        return [f"session_{i:03d}" for i in range(1, count + 1)]

    def add_sessions_to_group(self, session_ids: List[str]):
        """Add sessions to the annotation group and store group item IDs"""
        self.log_info("=== Adding Sessions to Group ===")

        group_items = {"session_ids": session_ids}

        self.log_info(f"Adding {len(session_ids)} sessions to group")
        endpoint = f"/annotation-groups/{self.annotation_group_id}/items"
        result = self.api_call("POST", endpoint, group_items, "annotation group items")

        if result:
            # Get the created group items to map session_ids to group_item_ids
            # First, retrieve the group items to get their IDs
            get_endpoint = f"/annotation-groups/{self.annotation_group_id}/items"
            items_result = self.api_call(
                "GET", get_endpoint, None, "retrieve group items"
            )

            if items_result and "data" in items_result:
                for item in items_result["data"]:
                    session_id = item["session_id"]
                    group_item_id = item["id"]
                    self.group_item_ids[session_id] = group_item_id
                    self.log_info(
                        f"Mapped session {session_id} to group item {group_item_id}"
                    )

        return result

    def add_sessions_to_llm_group(self, session_ids: List[str]):
        """Add sessions to the LLM annotation group and store group item IDs"""
        self.log_info("=== Adding Sessions to LLM Group ===")

        group_items = {"session_ids": session_ids}

        self.log_info(f"Adding {len(session_ids)} sessions to LLM group")
        endpoint = f"/annotation-groups/{self.llm_annotation_group_id}/items"
        result = self.api_call(
            "POST", endpoint, group_items, "LLM annotation group items"
        )

        if result:
            # Get the created group items to map session_ids to group_item_ids
            get_endpoint = f"/annotation-groups/{self.llm_annotation_group_id}/items"
            items_result = self.api_call(
                "GET", get_endpoint, None, "retrieve LLM group items"
            )

            if items_result and "data" in items_result:
                for item in items_result["data"]:
                    session_id = item["session_id"]
                    group_item_id = item["id"]
                    self.llm_group_item_ids[session_id] = group_item_id
                    self.log_info(
                        f"Mapped LLM session {session_id} to group item {group_item_id}"
                    )

        return result

    def generate_majority_baseline(
        self, session_ids: List[str]
    ) -> Dict[str, Dict[str, Any]]:
        """Generate majority baseline for each session based on collective behavior"""
        self.log_info("=== Generating Majority Baseline ===")

        # Session genres with their probabilities
        genres = ["product_info", "credit_card", "refund", "account", "other"]

        majority_baseline = {}

        for session_id in session_ids:
            # Generate Session Success majority (70% sessions are successful)
            majority_success = random.randint(1, 100) <= 70

            # Generate Session Genre majority (uniform distribution)
            majority_genre = random.choice(genres)

            majority_baseline[session_id] = {
                "success": majority_success,
                "genre": majority_genre,
            }

        self.log_info(f"Generated majority baseline for {len(session_ids)} sessions")
        return majority_baseline

    def generate_annotations(self, session_ids: List[str]):
        """Generate annotations based on reviewer profiles with majority agreement"""
        self.log_info("=== Generating Annotations ===")

        # Reviewer configurations: (accuracy%, participation%)
        reviewers = {
            "reviewer_1": (90, 95),
            "reviewer_2": (88, 92),
            "reviewer_3": (85, 90),
            "reviewer_4": (60, 90),  # Deviates from majority
        }

        # Generate majority baseline for all sessions
        majority_baseline = self.generate_majority_baseline(session_ids)

        total_annotations = 0

        for reviewer_id, (accuracy, participation) in reviewers.items():
            self.log_info(
                f"Generating annotations for {reviewer_id} "
                f"(accuracy: {accuracy}%, participation: {participation}%)"
            )

            reviewer_annotations = 0

            for session_id in session_ids:
                # Check if reviewer participates (based on participation rate)
                if random.randint(1, 100) > participation:
                    continue

                # Get majority values for this session
                majority_success = majority_baseline[session_id]["success"]
                majority_genre = majority_baseline[session_id]["genre"]

                # Generate Session Success annotation based on accuracy
                # Accuracy determines agreement with majority
                if random.randint(1, 100) <= accuracy:
                    success_value = majority_success  # Agree with majority
                else:
                    success_value = not majority_success  # Disagree

                # Create Session Success annotation
                success_annotation = {
                    "observation_id": session_id,
                    "observation_type": "session",
                    "observation_kind": "session",
                    "session_id": session_id,
                    "reviewer_id": reviewer_id,
                    "annotation_type_id": self.session_success_type_id,
                    "group_item_id": self.group_item_ids.get(session_id),
                    "annotation_value": json.dumps(success_value),
                    "input": "",
                    "input_type": "text",
                    "output": "",
                    "output_type": "text",
                    "comment": f"Session success annotation by {reviewer_id}",
                }

                result = self.api_call(
                    "POST",
                    "/annotations",
                    success_annotation,
                    f"Session Success annotation for {session_id} by {reviewer_id}",
                )
                if result:
                    reviewer_annotations += 1
                    total_annotations += 1

                # Generate Session Genre annotation based on accuracy
                # Session genres
                genres = ["product_info", "credit_card", "refund", "account", "other"]

                # Accuracy determines agreement with majority
                if random.randint(1, 100) <= accuracy:
                    genre_value = majority_genre  # Agree with majority
                else:
                    # Disagree with majority - pick different genre
                    available_genres = [g for g in genres if g != majority_genre]
                    genre_value = random.choice(available_genres)

                genre_annotation = {
                    "observation_id": session_id,
                    "observation_type": "session",
                    "observation_kind": "session",
                    "session_id": session_id,
                    "reviewer_id": reviewer_id,
                    "annotation_type_id": self.session_genre_type_id,
                    "group_item_id": self.group_item_ids.get(session_id),
                    "annotation_value": json.dumps(genre_value),
                    "input": "",
                    "input_type": "text",
                    "output": "",
                    "output_type": "text",
                    "comment": f"Session genre annotation by {reviewer_id}",
                }

                result = self.api_call(
                    "POST",
                    "/annotations",
                    genre_annotation,
                    f"Session Genre annotation for {session_id} by {reviewer_id}",
                )
                if result:
                    reviewer_annotations += 1
                    total_annotations += 1

            self.log_success(
                f"Generated {reviewer_annotations} annotations " f"for {reviewer_id}"
            )

        self.log_success(f"Generated total of {total_annotations} annotations")

    def generate_llm_observations(self, session_ids: List[str]) -> Dict[str, List[str]]:
        """Generate 2 LLM observation IDs for each session"""
        llm_observations = {}
        for session_id in session_ids:
            llm_observations[session_id] = [
                f"{session_id}_llm_001",
                f"{session_id}_llm_002",
            ]
        return llm_observations

    def generate_llm_hallucination_baseline(
        self, llm_observations: Dict[str, List[str]]
    ) -> Dict[str, bool]:
        """Generate majority baseline for LLM hallucination (95% agreement)"""
        self.log_info("=== Generating LLM Hallucination Baseline ===")

        hallucination_baseline = {}

        for session_id, observation_ids in llm_observations.items():
            for obs_id in observation_ids:
                # Generate baseline: 30% chance of hallucination
                hallucination_baseline[obs_id] = random.randint(1, 100) <= 30

        self.log_info(
            f"Generated hallucination baseline for {len(hallucination_baseline)} LLM observations"
        )
        return hallucination_baseline

    def generate_llm_annotations(self, session_ids: List[str]):
        """Generate LLM hallucination annotations"""
        self.log_info("=== Generating LLM Annotations ===")

        # Generate LLM observations (2 per session)
        llm_observations = self.generate_llm_observations(session_ids)

        # Generate majority baseline
        hallucination_baseline = self.generate_llm_hallucination_baseline(
            llm_observations
        )

        # Reviewer configurations for LLM annotations
        llm_reviewers = {
            "reviewer_1": (
                95,
                100,
            ),  # First 3 reviewers: 95% accuracy, 100% participation
            "reviewer_2": (95, 100),
            "reviewer_3": (95, 100),
            "reviewer_4": (
                45,
                50,
            ),  # Last reviewer: 45% accuracy (55% wrong), 50% participation
        }

        total_llm_annotations = 0

        for reviewer_id, (accuracy, participation) in llm_reviewers.items():
            self.log_info(
                f"Generating LLM annotations for {reviewer_id} "
                f"(accuracy: {accuracy}%, participation: {participation}%)"
            )

            reviewer_annotations = 0

            for session_id, observation_ids in llm_observations.items():
                for obs_id in observation_ids:
                    # Check if reviewer participates
                    if random.randint(1, 100) > participation:
                        continue

                    # Get majority baseline for this observation
                    majority_hallucination = hallucination_baseline[obs_id]

                    # Generate annotation based on accuracy
                    if random.randint(1, 100) <= accuracy:
                        hallucination_value = (
                            majority_hallucination  # Agree with majority
                        )
                    else:
                        hallucination_value = not majority_hallucination  # Disagree

                    # Create LLM Hallucination annotation
                    hallucination_annotation = {
                        "observation_id": obs_id,
                        "observation_type": "trace",  # LLM observations are traces
                        "observation_kind": "llm",
                        "session_id": session_id,
                        "reviewer_id": reviewer_id,
                        "annotation_type_id": self.hallucination_type_id,
                        "group_item_id": self.llm_group_item_ids.get(session_id),
                        "annotation_value": json.dumps(hallucination_value),
                        "input": f"LLM input for {obs_id}",
                        "input_type": "text",
                        "output": f"LLM output for {obs_id}",
                        "output_type": "text",
                        "comment": f"LLM hallucination annotation by {reviewer_id}",
                    }

                    result = self.api_call(
                        "POST",
                        "/annotations",
                        hallucination_annotation,
                        f"LLM Hallucination annotation for {obs_id} by {reviewer_id}",
                    )

                    if result:
                        reviewer_annotations += 1
                        total_llm_annotations += 1

            self.log_success(
                f"Generated {reviewer_annotations} LLM annotations "
                f"for {reviewer_id}"
            )

        self.log_success(f"Generated total of {total_llm_annotations} LLM annotations")

    def create_annotation_datasets(self):
        """Create the annotation datasets"""
        self.log_info("=== Creating Annotation Datasets ===")

        # Dataset 1: ds_1 with no tags and 3 items
        ds1 = {
            "name": "ds_1",
            "tags": []
        }

        ds1_result = self.api_call(
            "POST",
            "/annotation-datasets",
            ds1,
            "Dataset ds_1"
        )
        self.dataset_ds1_id = ds1_result["id"] if ds1_result else None

        # Dataset 2: ds_2 with tags and 11 items
        ds2 = {
            "name": "ds_2",
            "tags": ["test_2_1", "test_2_2"]
        }

        ds2_result = self.api_call(
            "POST",
            "/annotation-datasets",
            ds2,
            "Dataset ds_2"
        )
        self.dataset_ds2_id = ds2_result["id"] if ds2_result else None

        # Dataset 3: ds_20 with tags and 51 items
        ds20 = {
            "name": "ds_20",
            "tags": ["test_20_A", "test_2_B"]
        }

        ds20_result = self.api_call(
            "POST",
            "/annotation-datasets",
            ds20,
            "Dataset ds_20"
        )
        self.dataset_ds20_id = ds20_result["id"] if ds20_result else None

        # Import items into datasets
        if self.dataset_ds1_id:
            self.import_dataset_items(self.dataset_ds1_id, 3, "ds_1")

        if self.dataset_ds2_id:
            self.import_dataset_items(self.dataset_ds2_id, 11, "ds_2")

        if self.dataset_ds20_id:
            self.import_dataset_items(self.dataset_ds20_id, 51, "ds_20")

        return True

    def import_dataset_items(self, dataset_id, count, dataset_name):
        """Import items into a dataset"""
        self.log_info(f"Importing {count} items into dataset {dataset_name}")

        items = []
        for i in range(count):
            item = {
                "session_id": f"session_{dataset_name}_{i+1}",
                "session_date": f"2024-{random.randint(1,12):02d}-{random.randint(1,28):02d}T{random.randint(0,23):02d}:{random.randint(0,59):02d}:{random.randint(0,59):02d}Z" if random.random() > 0.1 else None,
                "input": f"Sample input for {dataset_name} item {i+1}",
                "output": f"Sample output for {dataset_name} item {i+1}",
                "expected_output": f"Expected output for {dataset_name} item {i+1}",
                "tags": [f"tag_{dataset_name}_{j}" for j in range(random.randint(0, 3))]
            }
            items.append(item)

        import_result = self.api_call(
            "POST",
            f"/annotation-datasets/{dataset_id}/import",
            items,
            f"Import items into dataset {dataset_name}"
        )

        if import_result:
            self.log_success(f"Imported items into dataset {dataset_name}: {import_result.get('status', {}).get('state', 'UNKNOWN')}")

    def run(self):
        """Run the complete data population process"""
        self.log_info("Starting annotation sample data population...")

        try:
            # 1. Create annotation types
            if not self.create_annotation_types():
                self.log_error("Failed to create annotation types")
                return False

            # 2. Create annotation datasets
            if not self.create_annotation_datasets():
                self.log_error("Failed to create annotation datasets")
                return False

            # 3. Create annotation group
            if not self.create_annotation_group():
                self.log_error("Failed to create annotation group")
                return False

            # 4. Generate and add sessions
            session_ids = self.generate_session_ids(30)
            if not self.add_sessions_to_group(session_ids):
                self.log_error("Failed to add sessions to group")
                return False

            # 5. Generate annotations
            self.generate_annotations(session_ids)

            # 6. Create LLM annotation group
            if not self.create_llm_annotation_group():
                self.log_error("Failed to create LLM annotation group")
                return False

            # 7. Generate and add sessions to LLM group
            if not self.add_sessions_to_llm_group(session_ids):
                self.log_error("Failed to add sessions to LLM group")
                return False

            # 8. Generate LLM annotations
            self.generate_llm_annotations(session_ids)

            # 9. Summarize

            self.log_success("=== Sample Data Population Complete! ===")
            self.log_info("")
            self.log_info("Summary:")
            self.log_info("- Created 3 annotation types")
            self.log_info("- Created 3 annotation datasets")
            self.log_info("  * ds_1: 3 items, no tags")
            self.log_info("  * ds_2: 11 items, tags: test_2_1, test_2_2")
            self.log_info("  * ds_20: 51 items, tags: test_20_A, test_2_B")
            self.log_info(
                f"- Created session annotation group: {self.annotation_group_id}"
            )
            self.log_info(
                f"- Created LLM annotation group: {self.llm_annotation_group_id}"
            )
            self.log_info("- Added 30 sessions to both groups")
            self.log_info("- Generated session annotations from 4 reviewers")
            self.log_info("  * reviewer_1: 90% accuracy, 95% participation")
            self.log_info("  * reviewer_2: 88% accuracy, 92% participation")
            self.log_info("  * reviewer_3: 85% accuracy, 90% participation")
            self.log_info("  * reviewer_4: 60% accuracy, 90% participation")
            self.log_info(
                "- Generated LLM hallucination annotations (2 obs per session)"
            )
            self.log_info("  * reviewer_1: 95% accuracy, 100% participation")
            self.log_info("  * reviewer_2: 95% accuracy, 100% participation")
            self.log_info("  * reviewer_3: 95% accuracy, 100% participation")
            self.log_info("  * reviewer_4: 45% accuracy, 50% participation")
            self.log_info("")
            self.log_info("You can now test the annotation endpoints!")
            session_group_endpoint = f"/annotation-groups/{self.annotation_group_id}"
            llm_group_endpoint = f"/annotation-groups/{self.llm_annotation_group_id}"
            self.log_info(
                f"Session group: curl '{self.api_base_url}{session_group_endpoint}'"
            )
            self.log_info(
                f"LLM group: curl '{self.api_base_url}{llm_group_endpoint}'"
            )

        except Exception as e:
            self.log_error(f"Failed to populate sample data: {str(e)}")
            return False

        return True


def main():
    """Main entry point"""
    # Allow override of API base URL via command line
    api_url = sys.argv[1] if len(sys.argv) > 1 else API_BASE_URL

    populator = AnnotationDataPopulator(api_url)
    success = populator.run()

    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
