"""Acceptance criteria"""
class AcceptanceCriteria:
    def is_accepted(self, package): return package.validation_results.get("overall_passed", False)
