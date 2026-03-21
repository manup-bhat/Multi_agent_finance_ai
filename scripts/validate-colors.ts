#!/usr/bin/env node

/**
 * Color Validation Script
 * Validates all color schemes for WCAG compliance
 * Run: npx ts-node scripts/validate-colors.ts
 */

import { validatePalette, VALIDATED_COLOR_SCHEMES } from '../lib/color-validation';
import { CHART_COLORS } from '../lib/chart-theme';

console.log('\n' + '='.repeat(60));
console.log('COLOR CONTRAST VALIDATION REPORT');
console.log('='.repeat(60) + '\n');

// 1. Validate palette
console.log('📊 PALETTE VALIDATION');
console.log('-'.repeat(60));
const validation = validatePalette();

Object.entries(VALIDATED_COLOR_SCHEMES).forEach(([key, scheme]) => {
  const status = scheme.acceptable ? '✓ PASS' : '✗ FAIL';
  const level = scheme.contrast.level;
  const ratio = scheme.contrast.ratio;

  console.log(`${status} [${level}] ${scheme.name.padEnd(30)} ${ratio}:1`);
  if (!scheme.acceptable) {
    console.log(`     ⚠️  Insufficient contrast for WCAG AA (need 4.5:1)`);
  }
});

console.log('\n');

// 2. Summary
console.log('📈 SUMMARY');
console.log('-'.repeat(60));
console.log(`Total Schemes: ${Object.keys(VALIDATED_COLOR_SCHEMES).length}`);
console.log(`Valid (AA+): ${Object.values(VALIDATED_COLOR_SCHEMES).filter((s) => s.acceptable).length}`);
console.log(`Invalid: ${Object.values(VALIDATED_COLOR_SCHEMES).filter((s) => !s.acceptable).length}`);
console.log(`\nOverall Status: ${validation.valid ? '✓ COMPLIANT' : '✗ NON-COMPLIANT'}`);

if (validation.issues.length > 0) {
  console.log('\n⚠️  Issues Found:');
  validation.issues.forEach((issue) => console.log(`  - ${issue}`));
}

console.log('\n');

// 3. Chart colors reference
console.log('🎨 CHART COLORS REFERENCE');
console.log('-'.repeat(60));
Object.entries(CHART_COLORS).forEach(([key, color]) => {
  console.log(`${key.padEnd(20)} ${color}`);
});

console.log('\n');

// 4. Contrast breakdown by category
console.log('📋 CONTRAST BREAKDOWN');
console.log('-'.repeat(60));

const categories = {
  'Light Mode': ['lightPrimary', 'lightSecondary', 'lightTertiary'],
  'Dark Mode': ['darkPrimary', 'darkSecondary', 'darkTertiary'],
  'Semantic Colors': ['bullish', 'bullishInvert', 'bearish', 'bearishInvert', 'neutral', 'neutralInvert', 'warning', 'warningInvert'],
  'Saffron (Brand)': ['saffron', 'saffronLight', 'saffronInvert'],
};

Object.entries(categories).forEach(([category, schemes]) => {
  console.log(`\n${category}:`);
  schemes.forEach((schemeKey) => {
    const scheme = VALIDATED_COLOR_SCHEMES[schemeKey as keyof typeof VALIDATED_COLOR_SCHEMES];
    if (scheme) {
      const wcagLevel = scheme.contrast.wcagAAA ? 'AAA' : scheme.contrast.wcagAA ? 'AA' : 'FAIL';
      console.log(
        `  ${scheme.name.padEnd(25)} ${scheme.contrast.ratio}:1 [${wcagLevel}] ${scheme.acceptable ? '✓' : '✗'}`,
      );
    }
  });
});

console.log('\n' + '='.repeat(60));
console.log(validation.valid ? '✓ ALL CHECKS PASSED' : '✗ VALIDATION FAILED');
console.log('='.repeat(60) + '\n');

// Exit with appropriate code
process.exit(validation.valid ? 0 : 1);
