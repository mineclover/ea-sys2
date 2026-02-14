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
  assert.equal(typeof summary.fingerprint, 'string');
  assert.equal(summary.fingerprint.length, 64);
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
  assert.equal(typeof model.fingerprint, 'string');
  assert.equal(model.fingerprint.length, 64);
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

test('listKernelFeedbackTargets returns canonical targets', () => {
  const model = sdk.buildKernelContractModel();
  const all = sdk.listKernelFeedbackTargets(model);
  assert.equal(all.length > 0, true);
  assert.equal(all.some((row) => row.canonicalId === 'rule:mem-01'), true);
  assert.equal(
    all.some(
      (row) =>
        row.canonicalId ===
        'layer_constraint:lc-00-l4-l4-association',
    ),
    true,
  );

  const onlyRules = sdk.listKernelFeedbackTargets(model, 'rule');
  assert.equal(onlyRules.every((row) => row.targetType === 'rule'), true);
});

test('evaluateKernelRelationship follows vector contract', () => {
  const model = sdk.buildKernelContractModel();
  for (const vector of model.bundle.vectors.vectors) {
    const evaluation = sdk.evaluateKernelRelationship(model, {
      sourceEntity: vector.triple[0],
      targetEntity: vector.triple[1],
      relation: vector.triple[2],
    });
    assert.equal(evaluation.allowed, vector.expected_verdict);
    assert.equal(evaluation.winnerRuleId, vector.expected_winner_rule_id);
  }
});

test('evaluateKernelRelationship returns constraint block details', () => {
  const model = sdk.buildKernelContractModel();
  const evaluation = sdk.evaluateKernelRelationship(model, {
    sourceEntity: 'event',
    targetEntity: 'event',
    relation: 'association',
  });

  assert.equal(evaluation.allowed, false);
  assert.equal(evaluation.reason, 'constraint_denied');
  assert.equal(evaluation.blockingConstraintId, 'lc-00-l4-l4-association');
});

test('buildLayerContractConvention returns package convention', () => {
  const convention = sdk.buildLayerContractConvention('Decision Layer');
  assert.equal(convention.layerSlug, 'decision_layer');
  assert.equal(convention.tsPackageName, '@ea-sys2/decision_layer-contract-sdk');
  assert.equal(convention.pyPackageName, 'ea-decision_layer-contract');
  assert.equal(convention.schemaFile, 'kernel_schema.snapshot.json');
});

test('composeKernelContractModel applies namespaced layer overlay rules', () => {
  const base = sdk.buildKernelContractModel();
  const composed = sdk.composeKernelContractModel(base, [
    {
      layerId: 'decision',
      explicitRules: [
        {
          id: 'allow-event-trigger-structure',
          source_pattern: 'event',
          target_pattern: 'structure',
          relation: 'triggering',
          valid: true,
          priority: 95,
          conditions: [],
          notes: 'decision layer override',
        },
      ],
    },
  ]);

  const evaluation = sdk.evaluateKernelRelationship(composed, {
    sourceEntity: 'event',
    targetEntity: 'structure',
    relation: 'triggering',
  });

  assert.equal(evaluation.allowed, true);
  assert.equal(evaluation.winnerRuleId, 'decision:allow-event-trigger-structure');
  assert.equal(composed.index.ruleById.has('decision:allow-event-trigger-structure'), true);
  assert.notEqual(composed.fingerprint, base.fingerprint);
});

test('composeKernelContractBundle replaces fallback rule per relation', () => {
  const base = sdk.loadKernelContractBundle();
  const composed = sdk.composeKernelContractBundle(base, [
    {
      layerId: 'infra',
      fallbackRules: [
        {
          id: 'fallback-membership-infra',
          source_pattern: '*',
          target_pattern: '*',
          relation: 'membership',
          valid: false,
          priority: 1,
          conditions: [],
          notes: 'infra fallback',
        },
      ],
    },
  ]);

  const fallback = composed.rules.fallback_rules.find(
    (row) => row.relation === 'membership',
  );
  assert.equal(fallback.id, 'infra:fallback-membership-infra');
  assert.equal(
    composed.rules.fallback_rules.filter((row) => row.relation === 'membership').length,
    1,
  );
});
