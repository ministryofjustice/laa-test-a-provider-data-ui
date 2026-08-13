const { setWorldConstructor } = require('@cucumber/cucumber');
const { chromium } = require('playwright');

class CustomWorld {
  async openBrowser() {
    this.browser = await chromium.launch({
      headless: process.env.HEADED !== 'true',
    });

    this.context = await this.browser.newContext({
      baseURL: process.env.BASE_URL || 'http://localhost:8020/',
      recordVideo: {
        dir: 'test-results/videos',
      },
    });

    this.page = await this.context.newPage();
  }
}

setWorldConstructor(CustomWorld);