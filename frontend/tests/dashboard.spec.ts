import { expect, test } from '@playwright/test';

test('unauthenticated workspace shows no invented financial data',async({page})=>{
  await page.route('**/api/**',route=>route.fulfill({status:401,body:'Authentication required'}));
  await page.goto('/');
  await expect(page.getByRole('heading',{name:'Mission Control.'})).toBeVisible();
  await expect(page.getByLabel('Owner password')).toBeVisible();
  await expect(page.getByText('No market observations loaded')).toBeVisible();
  await expect(page.getByText('No signal analysis available')).toBeVisible();
  await expect(page.getByText('$10,000')).toHaveCount(0);
});
test('mobile navigation and all ten sections are reachable',async({page})=>{
  await page.setViewportSize({width:390,height:844});
  await page.route('**/api/**',route=>route.fulfill({status:401,body:'Authentication required'}));
  await page.goto('/');
  await page.getByLabel('Open navigation').click();
  await page.getByRole('button',{name:'Live Markets',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Live Markets.'})).toBeVisible();
  await expect(page.getByRole('heading',{name:'Indicative swap estimates'})).toBeVisible();
  await page.getByLabel('Open navigation').click();
  await page.getByRole('button',{name:'Strategy Lab',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Walk-forward strategy lab'})).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBeTruthy();
});
