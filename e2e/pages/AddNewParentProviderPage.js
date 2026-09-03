import { expect } from '@playwright/test';
import BasePage from './BasePage.js';

class AddNewParentProviderPage extends BasePage {
    constructor(page) {
        super(page);
        this.pageHeading = this.page.locator('h1');
        this.providerNameInput = this.page.locator('#provider_name');
        this.chamberProviderType = this.page.locator('#provider_type');
        this.lspProviderType = this.page.locator('#provider_type-2');

    }
    async validatePageHeading() {
        await expect(this.pageHeading).toHaveText('Add a new parent provider');
    }

    async fillProviderName(providerName) {
        await this.providerNameInput.fill(providerName);
    }

    async selectChamberProviderType() {
        await this.chamberProviderType.check();
    }

    async selectLSPProviderType() {
        await this.lspProviderType.check();
    }

    async fillMandatoryFieldsForLSPProvider(providerName) {
        await this.fillProviderName(providerName);
        await this.selectLSPProviderType();
        await this.continueButton.click();
    }
}
export default AddNewParentProviderPage;