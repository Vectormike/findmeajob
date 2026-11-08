from findmeajob.agents.tailor import PAGE, clean_html, focused_posting

SAMPLE = """
"
<div class="head"><h1>Ada Lovelace</h1>
<div class="identity"><p>Engineer<br>London<br><a href="https://example.com" onclick="x">site</a></p>
<p class="summary">Builds things.</p></div></div>
<script>alert(1)</script>
<h2>Work Experience</h2>
<div class="role"><p class="role-line"><strong>Engineer</strong><span>Acme</span><span class="when">2020 - 2024</span></p>
<ul><li>Shipped it.</li></ul></div>
<h2>Skills</h2>
<div class="skills"><p><strong>Languages</strong><span>Go, SQL</span></p></div>
"""


def test_cv_html_keeps_the_resume_layout():
    html = clean_html(SAMPLE)
    assert "<script>" not in html and "onclick" not in html
    assert html.startswith('<div class="head">')
    for marker in ('class="identity"', 'class="summary"', 'class="role-line"', 'class="when"', 'class="skills"'):
        assert marker in html
    page = PAGE.format(body=html)
    assert "grid-template-columns: 1.25fr 1fr auto" in page
    assert "Ada Lovelace" in page


def test_myjobmag_posting_drops_page_navigation():
    posting = {
        "source": "myjobmag",
        "title": "DevOps Engineer",
        "company": "Acme",
        "description": (
            "Login Signup Employers Jobs Career Advice "
            "About the Role\nBuild cloud infrastructure.\nRequirements\nAWS and Kubernetes.\n"
            "Method of Application\nSign up for alerts and view other jobs."
        ),
    }
    text = focused_posting(posting)
    assert "About the Role" in text and "AWS and Kubernetes" in text
    assert "Login Signup" not in text and "Sign up for alerts" not in text
