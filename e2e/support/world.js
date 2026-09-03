import { setWorldConstructor } from '@cucumber/cucumber';
import { chromium } from 'playwright';

class CustomWorld {
  async openBrowser() {
    this.browser = await chromium.launch({
      headless: false,
    });

    this.context = await this.browser.newContext({
      baseURL: process.env.BASE_URL || 'http://localhost:8020/providers',
      recordVideo: {
        dir: 'test-results/videos',
      },
    });

    this.page = await this.context.newPage();
  }
}

setWorldConstructor(CustomWorld);