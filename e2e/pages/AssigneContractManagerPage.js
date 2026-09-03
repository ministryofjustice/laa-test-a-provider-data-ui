import BasePage from './BasePage.js';
class AssigneContractManagerPage extends BasePage {
    constructor(page) {
        super(page);
        this.contractManagerRadioButton = this.page.getByRole('radio');
        this.submitButton = this.page.getByRole('button', { name: 'Submit' });
        this.unknownButton = this.page.getByRole('button', { name: 'Unknown: Skip this step' });
    }

    async selectContractManagerOption() {

        const count = await this.contractManagerRadioButton.count();
        
        if (count>0){
        this.contractManagerRadioButton = this.contractManagerRadioButton.first();
        await this.contractManagerRadioButton.check();
        await this.submitButton.click();

        }else{
            console.log("No contract manager radio button found so selecting Unknown option");
            await this.unknownButton.click();

        }

        
    }
}
export default AssigneContractManagerPage;