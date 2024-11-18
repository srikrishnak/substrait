# SPDX-License-Identifier: Apache-2.0
import json
from collections import defaultdict

from tests.coverage.case_file_parser import load_all_testcases
from tests.coverage.extensions import Extension, error, FunctionRegistry


class FunctionTestCoverage:
    function_name: str
    test_count: int
    function_variant_coverage: defaultdict[str, int]

    def __init__(self, function_name):
        self.function_name = function_name
        self.test_count = 0
        self.function_variant_coverage = defaultdict(int)

    def update_coverage(self, function_variant, count):
        self.function_variant_coverage[function_variant] += count
        self.test_count += count

    def to_dict(self):
        return {
            "function_name": self.function_name,
            "test_count": self.test_count,
            "variants": [
                {"signature": variant, "test_count": count}
                for variant, count in self.function_variant_coverage.items()
            ],
        }


class FileTestCoverage:
    file_name: str
    test_count: int
    function_coverage: dict[str, FunctionTestCoverage]

    def __init__(self, file_name):
        self.file_name = file_name
        self.test_count = 0
        self.function_coverage = dict()

    def update_coverage(self, func_name, args, count):
        key = f"{func_name}({', '.join(args)})"
        if func_name not in self.function_coverage:
            self.function_coverage[func_name] = FunctionTestCoverage(func_name)
        self.function_coverage[func_name].update_coverage(key, count)
        self.test_count += count

    def to_dict(self):
        return {
            "file_name": self.file_name,
            "test_count": self.test_count,
            "function_coverage": [
                func_coverage.to_dict()
                for func_name, func_coverage in self.function_coverage.items()
            ],
        }


class TestCoverage:
    file_coverage: dict[str, FileTestCoverage]
    test_count: int
    num_tests_with_no_matching_function: int
    num_covered_function_variants: int
    total_function_variants: int

    def __init__(self, ext_uris):
        self.file_coverage = dict()
        self.test_count = 0
        self.num_tests_with_no_matching_function = 0
        self.num_covered_function_variants = 0
        self.total_function_variants = 0
        for ext_uri in ext_uris:
            self.file_coverage[ext_uri] = FileTestCoverage(ext_uri)

    def update_coverage(self, ext_uri, function, args, count):
        if ext_uri not in self.file_coverage:
            self.file_coverage[ext_uri] = FileTestCoverage(ext_uri)
        self.file_coverage[ext_uri].update_coverage(function, args, count)
        self.test_count += count

    def compute_coverage(self):
        for file_coverage in self.file_coverage.values():
            for function_coverage in file_coverage.function_coverage.values():
                for test_count in function_coverage.function_variant_coverage.values():
                    if test_count > 0:
                        self.num_covered_function_variants += 1
                    self.total_function_variants += 1

    def to_dict(self):
        return {
            "file_coverage": [
                file_coverage.to_dict() for file_coverage in self.file_coverage.values()
            ],
            "test_count": self.test_count,
            "num_tests_with_no_matching_function": self.num_tests_with_no_matching_function,
            "num_covered_function_variants": self.num_covered_function_variants,
            "total_function_variants": self.total_function_variants,
        }

    def to_json(self):
        return json.dumps(self.to_dict(), indent=2)


def update_test_count(test_case_files: list, function_registry: FunctionRegistry):
    num_tests_with_no_matching_function = 0
    for test_file in test_case_files:
        for test_case in test_file.testcases:
            function_variant = function_registry.get_function(
                test_case.func_name,
                test_file.include,
                test_case.get_arg_types(),
                test_case.get_return_type(),
            )
            if function_variant:
                if (
                    not test_case.is_return_type_error()
                    and not function_registry.is_same_type(
                        function_variant.return_type, test_case.get_return_type()
                    )
                ):
                    error(
                        f"Return type mismatch in function {test_case.get_signature()}: "
                        f"{function_variant.return_type} != {test_case.get_return_type()}"
                    )
                    num_tests_with_no_matching_function += 1
                    continue
                function_variant.increment_test_count()
            else:
                error(f"Function not found: {test_case.get_signature()}")
                num_tests_with_no_matching_function += 1
    return num_tests_with_no_matching_function


def get_test_coverage(test_files, function_registry):
    coverage = TestCoverage(function_registry.get_extension_list())
    coverage.num_tests_with_no_matching_function = update_test_count(
        test_files, function_registry
    )
    function_registry.fill_coverage(coverage)
    coverage.compute_coverage()
    return coverage


if __name__ == "__main__":
    all_test_files = load_all_testcases("../cases")
    default_function_registry = Extension.read_substrait_extensions("../../extensions")
    test_coverage = get_test_coverage(all_test_files, default_function_registry)
    print(test_coverage.to_json())
