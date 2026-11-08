from pathlib import Path

import pytest
from playwright.async_api import async_playwright

from findmeajob.tools.browser import FormSession
from findmeajob.tools.browser_ats import STRATEGIES


async def test_form_session_handles_custom_controls_and_multiple_steps(tmp_path: Path):
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome", headless=True)
        page = await browser.new_page()
        await page.set_content(
            """
            <main id="form">
              <label>Name <input name="name" required></label>
              <div role="combobox" contenteditable="true" aria-label="Location"
                   aria-controls="locations" aria-required="true"></div>
              <div id="locations" role="listbox"><div role="option">Berlin</div></div>
              <button type="button" onclick="stepTwo()">Next</button>
            </main>
            <script>
              function stepTwo() {
                document.querySelector('main').innerHTML = `
                  <div role="radiogroup" aria-label="Work authorization" aria-required="true">
                    <div role="radio">Yes</div><div role="radio">No</div>
                  </div>
                  <label>Why us? <textarea required></textarea></label>
                  <button type="submit" onclick="submitted(event)">Submit application</button>`;
              }
              function submitted(event) {
                event.preventDefault();
                document.body.innerHTML = '<h1>Thanks for applying</h1>';
              }
            </script>
            """
        )
        session = FormSession(page)

        first = await session.fields()
        assert [field["type"] for field in first] == ["input", "combobox"]
        await session.fill(first, {"f0": "Ada Lovelace", "f1": "Berlin"}, tmp_path / "cv.pdf")
        assert (await session.advance())["status"] == "advanced"

        second = await session.fields()
        assert [field["type"] for field in second] == ["radio", "textarea"]
        await session.fill(second, {"g0": "Yes", "f3": "I build reliable systems."}, tmp_path / "cv.pdf")
        outcome = await session.advance()

        assert outcome["status"] == "submitted"
        assert outcome["confirmation"]["confirmed"] == "yes"
        await browser.close()


@pytest.mark.parametrize(
    ("strategy_name", "button", "success"),
    [
        ("greenhouse", '<button id="submit_app">Apply</button>', '<p id="application_confirmation">Done</p>'),
        ("lever", '<button data-qa="submit-button">Apply</button>', '<p data-qa="application-success">Done</p>'),
        ("ashby", '<button data-testid="submit-job">Apply</button>', '<p data-testid="success">Done</p>'),
        (
            "workday",
            '<button data-automation-id="bottom-navigation-submit-button">Apply</button>',
            '<p data-automation-id="applicationConfirmation">Done</p>',
        ),
    ],
)
async def test_ats_submit_and_confirmation_selectors(strategy_name: str, button: str, success: str):
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome", headless=True)
        page = await browser.new_page()
        await page.set_content(
            f"""
            <form onsubmit="event.preventDefault(); this.hidden=true; document.querySelector('p').hidden=false">
              <label>Name <input required></label><label>Email <input required></label>{button}
            </form>
            {success.replace('>', ' hidden>', 1)}
            """
        )
        session = FormSession(page)
        session.strategy = next(strategy for strategy in STRATEGIES if strategy.name == strategy_name)
        fields = await session.fields()
        await session.fill(fields, {"f0": "Ada", "f1": "ada@example.com"}, Path("cv.pdf"))

        outcome = await session.advance()

        assert outcome["status"] == "submitted"
        await browser.close()
