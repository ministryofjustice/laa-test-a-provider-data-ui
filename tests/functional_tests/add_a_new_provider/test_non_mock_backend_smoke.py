import os
import re
import uuid

import pytest
from flask import url_for
from playwright.sync_api import Page, expect

from app.pda.mock_api import MockProviderDataApi

pytestmark = pytest.mark.skipif(
    os.environ.get("TEST_USE_REAL_PDA", "false").lower() != "true",
    reason="Set TEST_USE_REAL_PDA=true to run non-mock backend smoke tests.",
)


@pytest.mark.usefixtures("live_server")
def test_real_backend_lsp_create_smoke(app, page: Page):
    pda = app.extensions["pda"]
    assert not isinstance(pda, MockProviderDataApi)

    unique_suffix = uuid.uuid4().hex[:8]
    unique_digits = f"{int(unique_suffix, 16) % 10_000_000:07d}"
    companies_house_number = f"{int(unique_suffix, 16) % 100_000_000:08d}"
    provider_name = f"DSTEW2129 Smoke LSP {unique_suffix}"
    liaison_email = f"smoke.tester+{unique_suffix}@test.example.com"
    account_number = unique_digits
    account_name = f"Smoke Test Account {unique_suffix}"

    page.goto(url_for("main.add_parent_provider", _external=True))
    page.get_by_role("textbox", name="Provider name").fill(provider_name)
    page.get_by_role("radio", name="Legal services provider").click()
    page.get_by_role("button", name="Continue").click()

    expect(page.get_by_role("heading", name="Legal services provider details")).to_be_visible()
    page.get_by_role("radio", name="Limited company").click()
    page.locator("input[id='indemnity_received_date-day']").fill("19")
    page.locator("input[id='indemnity_received_date-month']").fill("8")
    page.locator("input[id='indemnity_received_date-year']").fill("2026")
    page.get_by_role("textbox", name="Companies House number").fill(companies_house_number)
    page.get_by_role("button", name="Continue").click()

    expect(page.get_by_role("heading", name="Head office contact details")).to_be_visible()
    page.get_by_role("textbox", name="Address line 1").fill("45 Kings Ride")
    page.get_by_role("textbox", name="Address line 2 (optional)").fill("Penn")
    page.get_by_role("textbox", name="Town or city").fill("High Wycombe")
    page.get_by_role("textbox", name="County (optional)").fill("Buckinghamshire")
    page.get_by_role("textbox", name="Postcode").fill("HP10 8BP")
    page.get_by_role("textbox", name="Telephone number").fill("07438342964")
    page.get_by_role("textbox", name="Email address").fill(liaison_email)
    page.get_by_role("textbox", name="DX number").fill("DX00001")
    page.get_by_role("textbox", name="DX centre").fill("Leeds DX Centre")
    page.get_by_role("button", name="Continue").click()

    expect(page.get_by_role("heading", name=re.compile(r"Head office: VAT registration number"))).to_be_visible()
    page.get_by_role("button", name="Continue").click()

    expect(page.get_by_role("heading", name="Head office: Bank account details")).to_be_visible()
    page.get_by_role("textbox", name="Account name").fill(account_name)
    page.get_by_role("textbox", name="Sort code").fill("030299")
    page.get_by_role("textbox", name="Account number").fill(account_number)
    page.get_by_role("button", name="Continue").click()

    expect(page.get_by_role("heading", name="Add liaison manager")).to_be_visible()
    page.get_by_role("textbox", name="First name").fill("Smoke")
    page.get_by_role("textbox", name="Last name").fill("Tester")
    page.get_by_role("textbox", name="Email address").fill(liaison_email)
    page.get_by_role("textbox", name="Telephone number").fill("07438342964")
    page.get_by_role("button", name="Continue").click()

    expect(page.get_by_role("heading", name="Assign contract manager")).to_be_visible()
    page.get_by_role("row", name=re.compile(r"Mr Default")).get_by_label("Select this row").click()
    page.get_by_role("button", name="Submit").click()

    expect(page).to_have_url(re.compile(r"/provider/\d+"))
    expect(page.get_by_role("heading", name=provider_name)).to_be_visible()
    expect(page.locator("dt", has_text="Constitutional status")).to_be_visible()
    expect(page.locator("dt", has_text="Companies House number")).to_be_visible()
    expect(page.locator("dt", has_text="Indemnity received date")).to_be_visible()
