import { defineConfig } from '@playwright/test';
export default defineConfig({testDir:'./tests',use:{baseURL:'http://127.0.0.1:3000',headless:true},webServer:{command:'npx serve out -l 3000',url:'http://127.0.0.1:3000',reuseExistingServer:!process.env.CI},reporter:'html'});
