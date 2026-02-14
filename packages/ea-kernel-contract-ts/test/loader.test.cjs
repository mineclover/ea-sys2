const assert = require('node:assert/strict');
const test = require('node:test');

const sdk = require('../lib');

test('loads contract bundle and summary', () => {
  const bundle = sdk.loadKernelContractBundle();
  assert.equal(bundle.schema.snapshot_kind, 'ea_kernel_schema_contract');
  assert.equal(bundle.rules.snapshot_kind, 'ea_kernel_rules_contract');
  assert.equal(bundle.vectors.snapshot_kind, 'ea_kernel_judgment_vectors_contract');

  const summary = sdk.summarizeKernelContract();
  assert.equal(summary.available, true);
  assert.equal(summary.kernelVersion, bundle.kernelVersion);
  assert.equal(summary.entityCount, bundle.schema.entities.length);
});

test('buildKernelContractModel builds stable indexes', () => {
  const model = sdk.buildKernelContractModel();
  assert.equal(model.index.entityByName.has('structure'), true);
  assert.equal(model.index.relationByName.has('association'), true);
  assert.equal(model.index.ruleById.has('mem-01'), true);
  assert.equal(
    model.index.layerConstraintById.has('lc-00-l4-l4-association'),
    true,
  );
});

test('resolveKernelFeedbackTarget validates canonical ids', () => {
  const model = sdk.buildKernelContractModel();

  const okRule = sdk.resolveKernelFeedbackTarget('rule:mem-01', model);
  assert.equal(okRule.canonicalId, 'rule:mem-01');

  const okConstraint = sdk.resolveKernelFeedbackTarget(
    'layer_constraint:lc-00-l4-l4-association',
    model,
  );
  assert.equal(
    okConstraint.canonicalId,
    'layer_constraint:lc-00-l4-l4-association',
  );

  assert.throws(
    () => sdk.resolveKernelFeedbackTarget('rule:unknown-rule', model),
    /unknown rule target/,
  );
  assert.throws(
    () => sdk.resolveKernelFeedbackTarget('bad:mem-01', model),
    /unsupported feedback target type/,
  );
});

test('getEntityRequiredKeys resolves inherited ownership keys', () => {
  const model = sdk.buildKernelContractModel();
  const keys = sdk.getEntityRequiredKeys(model, 'structure');

  assert.equal(keys.includes('uid'), true);
  assert.equal(keys.includes('name'), true);
  assert.equal(keys.includes('qualified_name'), true);
  assert.equal(keys.includes('layer'), true);
});

test('validateKernelContractBundle detects duplicate layer constraint ids', () => {
  const bundle = sdk.loadKernelContractBundle({ validate: false });
  const duplicate = { ...bundle.rules.layer_constraints[0] };

  const mutated = {
    ...bundle,
    rules: {
      ...bundle.rules,
      layer_constraints: [...bundle.rules.layer_constraints, duplicate],
    },
  };

  const issues = sdk.validateKernelContractBundle(mutated);
  assert.equal(
    issues.some((issue) => issue.includes('rules.layer_constraints.id duplicated')),
    true,
  );
});
