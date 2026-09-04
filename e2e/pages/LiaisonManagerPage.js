
import BasePage from './BasePage.js';

class LiaisonManagerPage extends BasePage {
    constructor(page) {
        super(page);
        this.liaisonManagerFirstName = this.page.getByRole('textbox', { name: 'First name' });
        this.liaisonManagerLastName = this.page.getByRole('textbox', { name: 'Last name' });
        this.liaisonManagerEmailAddress = this.page.getByRole('textbox', { name: 'Email address' });
        this.liaisonManagerTelephoneNumber = this.page.getByRole('textbox', { name: 'Telephone number' });
    }
    async fillMandatoryFieldsForLiaisonManager(firstName, lastName, emailAddress, telephoneNumber) {
        await this.liaisonManagerFirstName.fill(firstName);
        await this.liaisonManagerLastName.fill(lastName);
        await this.liaisonManagerEmailAddress.fill(emailAddress);
        await this.liaisonManagerTelephoneNumber.fill(telephoneNumber);
        await this.continueButton.click();
    }
}
export default LiaisonManagerPage;