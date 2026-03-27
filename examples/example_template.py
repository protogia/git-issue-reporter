"""Example: Report Value-Error using template."""
from git_issue_reporter.decorators import report_on_error

@report_on_error(
    template="bug_report.md",
    labels=["bug", "example"],
)
def trigger():
    raise ValueError("fail")



if __name__=="__main__":
    trigger()