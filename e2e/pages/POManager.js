
import ProviderRecordsPage from "./ProviderRecordsPage.js";
import AddNewParentProviderPage from "./AddNewParentProviderPage.js";
import LegalServiceProviderDetailsPage from "./LegalServiceProviderDetailsPage.js";
import HeadOfficeContactDetailsPage from "./HeadOfficeContactDetailsPage.js";
import HeadOfficVatRegPage from "./HeadOfficVatRegPage.js";
import HeadOfficeBankDetailsPage from "./HeadOfficeBankDetailsPage.js";
import LiaisonManagerPage from "./LiaisonManagerPage.js";
import ProviderSuccessPage from "./ProviderSuccessPage.js";
import AssigneContractManagerPage from "./AssigneContractManagerPage.js";
class POManager {
    constructor(page) {
        this.page = page;
        this.providerRecordsPage = new ProviderRecordsPage(this.page);
        this.addNewParentProviderPage = new AddNewParentProviderPage(this.page);
        this.legalServiceProviderDetailsPage = new LegalServiceProviderDetailsPage(this.page);
        this.headOfficeContactDetailsPage = new HeadOfficeContactDetailsPage(this.page);  
        this.headOfficVatRegPage = new HeadOfficVatRegPage(this.page);  
        this.headOfficeBankDetailsPage = new HeadOfficeBankDetailsPage(this.page);
        this.liaisonManagerPage = new LiaisonManagerPage(this.page);
        this.providerSuccessPage = new ProviderSuccessPage(this.page);
        this.assigneContractManagerPage = new AssigneContractManagerPage(this.page);
    }

    getProviderRecordsPage() {
        return this.providerRecordsPage;
    }

    getAddNewParentProviderPage() {
        return this.addNewParentProviderPage;
    }
    getLegalServiceProviderDetailsPage() {
        return this.legalServiceProviderDetailsPage;
    }
    getHeadOfficeContactDetailsPage() {
        return this.headOfficeContactDetailsPage;
    }
    getHeadOfficVatRegPage() {
        return this.headOfficVatRegPage;
    }
    getHeadOfficeBankDetailsPage() {
        return this.headOfficeBankDetailsPage;
    }
    getLiaisonManagerPage() {
        return this.liaisonManagerPage;
    }
    getAssigneContractManagerPage() {
        return this.assigneContractManagerPage;
    }
    getProviderSuccessPage() {
        return this.providerSuccessPage;
    }
}
export default POManager;