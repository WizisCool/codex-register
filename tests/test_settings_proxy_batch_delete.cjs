const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const SETTINGS_JS_PATH = path.join(__dirname, '..', 'static', 'js', 'settings.js');

function createClassList() {
  const values = new Set();
  return {
    add(...items) {
      items.forEach((item) => values.add(item));
    },
    remove(...items) {
      items.forEach((item) => values.delete(item));
    },
    contains(item) {
      return values.has(item);
    },
  };
}

function createElementStub(overrides = {}) {
  return {
    value: '',
    checked: false,
    disabled: false,
    indeterminate: false,
    innerHTML: '',
    textContent: '',
    style: {},
    dataset: {},
    classList: createClassList(),
    addEventListener() {},
    removeEventListener() {},
    querySelectorAll() {
      return [];
    },
    querySelector() {
      return null;
    },
    reset() {},
    ...overrides,
  };
}

function createSandbox() {
  const elements = new Map();
  const proxyCheckboxes = [];
  const toastCalls = [];
  const apiCalls = [];

  function getElement(id) {
    if (!elements.has(id)) {
      elements.set(id, createElementStub({ id }));
    }
    return elements.get(id);
  }

  const sandbox = {
    console,
    setTimeout,
    clearTimeout,
    __proxyCheckboxes: proxyCheckboxes,
    __toastCalls: toastCalls,
    __apiCalls: apiCalls,
    document: {
      getElementById(id) {
        return getElement(id);
      },
      querySelectorAll(selector) {
        if (selector === '.proxy-checkbox') {
          return proxyCheckboxes;
        }
        if (selector === '.proxy-checkbox:checked') {
          return proxyCheckboxes.filter((checkbox) => checkbox.checked);
        }
        return [];
      },
      addEventListener() {},
    },
    window: null,
    api: {
      get: async () => ({ proxies: [] }),
      post: async (url, payload) => {
        apiCalls.push({ url, payload });
        if (url === '/settings/proxies/delete-disabled') {
          return { success: true, deleted_count: 2, message: '已删除 2 个禁用代理' };
        }
        return { success: true, message: `已删除 ${payload.ids.length} 个代理`, not_found_ids: [] };
      },
      patch: async () => ({ success: true }),
      delete: async () => ({ success: true }),
    },
    toast: {
      success(message) {
        toastCalls.push({ type: 'success', message });
      },
      error(message) {
        toastCalls.push({ type: 'error', message });
      },
      info(message) {
        toastCalls.push({ type: 'info', message });
      },
    },
    confirm: async () => true,
    format: {
      date(value) {
        return value || '-';
      },
      number(value) {
        return String(value ?? 0);
      },
    },
  };

  sandbox.window = sandbox;
  sandbox.globalThis = sandbox;
  vm.createContext(sandbox);
  vm.runInContext(fs.readFileSync(SETTINGS_JS_PATH, 'utf8'), sandbox, { filename: 'settings.js' });
  return sandbox;
}

test('updateSelectedProxies updates batch delete button state', () => {
  const sandbox = createSandbox();
  sandbox.__proxyCheckboxes.push(
    createElementStub({ checked: true, dataset: { id: '1' } }),
    createElementStub({ checked: false, dataset: { id: '2' } }),
    createElementStub({ checked: true, dataset: { id: '3' } }),
  );

  vm.runInContext('updateSelectedProxies()', sandbox);

  const batchDeleteBtn = sandbox.document.getElementById('batch-delete-proxies-btn');
  const selectAllProxies = sandbox.document.getElementById('select-all-proxies');

  assert.equal(batchDeleteBtn.disabled, false);
  assert.equal(batchDeleteBtn.textContent, '🗑️ 批量删除 (2)');
  assert.equal(selectAllProxies.checked, false);
  assert.equal(selectAllProxies.indeterminate, true);
});

test('handleBatchDeleteProxies posts selected proxy ids and reloads list', async () => {
  const sandbox = createSandbox();
  sandbox.__proxyCheckboxes.push(
    createElementStub({ checked: true, dataset: { id: '11' } }),
    createElementStub({ checked: true, dataset: { id: '12' } }),
  );

  vm.runInContext('updateSelectedProxies()', sandbox);
  vm.runInContext('loadProxies = async () => { globalThis.__reloaded = true; }', sandbox);

  await vm.runInContext('handleBatchDeleteProxies()', sandbox);

  assert.deepEqual(JSON.parse(JSON.stringify(sandbox.__apiCalls)), [
    {
      url: '/settings/proxies/batch-delete',
      payload: { ids: [11, 12] },
    },
  ]);
  assert.equal(sandbox.__reloaded, true);
  assert.equal(sandbox.__toastCalls.at(-1).type, 'success');
});

test('handleBatchDeleteProxies rejects empty selection without api call', async () => {
  const sandbox = createSandbox();

  await vm.runInContext('handleBatchDeleteProxies()', sandbox);

  assert.deepEqual(JSON.parse(JSON.stringify(sandbox.__apiCalls)), []);
  assert.equal(sandbox.__toastCalls.at(-1).type, 'error');
  assert.equal(sandbox.__toastCalls.at(-1).message, '请先选择要删除的代理');
});

test('handleBatchDeleteProxies stops when user cancels confirmation', async () => {
  const sandbox = createSandbox();
  sandbox.confirm = async () => false;
  sandbox.__proxyCheckboxes.push(
    createElementStub({ checked: true, dataset: { id: '21' } }),
  );

  vm.runInContext('updateSelectedProxies()', sandbox);
  await vm.runInContext('handleBatchDeleteProxies()', sandbox);

  assert.deepEqual(JSON.parse(JSON.stringify(sandbox.__apiCalls)), []);
  assert.equal(sandbox.__toastCalls.length, 0);
});

test('updateProxyBatchActions enables delete-disabled button based on disabled count', () => {
  const sandbox = createSandbox();

  vm.runInContext('disabledProxyCount = 3; updateProxyBatchActions()', sandbox);

  const deleteDisabledBtn = sandbox.document.getElementById('delete-disabled-proxies-btn');
  assert.equal(deleteDisabledBtn.disabled, false);
  assert.equal(deleteDisabledBtn.textContent, '🧹 删除禁用项 (3)');
});

test('handleDeleteDisabledProxies posts dedicated route and reloads list', async () => {
  const sandbox = createSandbox();
  vm.runInContext('disabledProxyCount = 2', sandbox);
  vm.runInContext('loadProxies = async () => { globalThis.__reloadedDisabled = true; }', sandbox);

  await vm.runInContext('handleDeleteDisabledProxies()', sandbox);

  assert.deepEqual(JSON.parse(JSON.stringify(sandbox.__apiCalls)), [
    {
      url: '/settings/proxies/delete-disabled',
    },
  ]);
  assert.equal(sandbox.__reloadedDisabled, true);
  assert.equal(sandbox.__toastCalls.at(-1).message, '已删除 2 个禁用代理');
});

test('handleDeleteDisabledProxies rejects when there are no disabled proxies', async () => {
  const sandbox = createSandbox();

  await vm.runInContext('handleDeleteDisabledProxies()', sandbox);

  assert.deepEqual(JSON.parse(JSON.stringify(sandbox.__apiCalls)), []);
  assert.equal(sandbox.__toastCalls.at(-1).message, '当前没有可删除的禁用代理');
});

test('handleDeleteDisabledProxies stops when user cancels confirmation', async () => {
  const sandbox = createSandbox();
  sandbox.confirm = async () => false;
  vm.runInContext('disabledProxyCount = 2', sandbox);

  await vm.runInContext('handleDeleteDisabledProxies()', sandbox);

  assert.deepEqual(JSON.parse(JSON.stringify(sandbox.__apiCalls)), []);
  assert.equal(sandbox.__toastCalls.length, 0);
});





