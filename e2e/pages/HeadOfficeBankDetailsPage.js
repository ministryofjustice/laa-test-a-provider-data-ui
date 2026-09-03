import BasePage from './BasePage.js';
class HeadOfficeBankDetailsPage extends BasePage {
    constructor(page) {
        super(page);
        this.accountNameInput = this.page.getByRole('textbox', { name: 'Account name' });
        this.sortCodeInput = this.page.getByRole('textbox', { name: 'Sort code' });
        this.accountNumberInput = this.page.getByRole('textbox', { name: 'Account number' });
    }

    async fillMandatoryFieldsForHeadOfficeBankDetails(accountName, sortCode, accountNumber) {
        await this.accountNameInput.fill(accountName);
        await this.sortCodeInput.fill(sortCode);
        await this.accountNumberInput.fill(accountNumber);
        await this.continueButton.click();
    }
}
export default HeadOfficeBankDetailsPage;