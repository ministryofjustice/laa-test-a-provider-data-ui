import { expect } from "@playwright/test";

class ProviderSuccessPage {
    constructor(page) {
        this.page = page;
        this.successMessageLocator = this.page.locator('#govuk-notification-banner-title');
        
    }

    async verifySuccessMessage() {
        await this.successMessageLocator.click();
        await expect(this.successMessageLocator).toHaveText('Success');
    }
}

export default ProviderSuccessPage;