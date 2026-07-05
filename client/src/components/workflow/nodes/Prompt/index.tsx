import React from 'react';
import { FlowNodeRegistry, ValidateTrigger } from '@flowgram.ai/free-layout-editor';

export const PromptNodeRegistry: FlowNodeRegistry = {
  type: 'prompt',
  meta: {
    title: 'Prompt',
    defaultPorts: [{ type: 'output' }, { type: 'input' }],
  },
  formMeta: {
    validateTrigger: ValidateTrigger.onChange,
    validate: {
      prompt: ({ value }) => (value ? undefined : '提示词必填'),
    },
    render: ({ form }) => (
      <div>
        <form.Field name="prompt">
          {(field) => (
            <textarea
              {...field.field}
              placeholder="提示词内容，支持 {{nodeId.outputKey}} 变量插值"
              rows={4}
              style={{ width: '100%', marginBottom: 8 }}
            />
          )}
        </form.Field>
        <form.Field name="temperature">
          {(field) => <input {...field.field} type="number" step="0.1" placeholder="温度（默认 0.7）" style={{ width: '100%', marginBottom: 8 }} />}
        </form.Field>
        <form.Field name="model">
          {(field) => <input {...field.field} placeholder="模型名（默认 qwen-plus）" style={{ width: '100%', marginBottom: 8 }} />}
        </form.Field>
        <form.Field name="maxTokens">
          {(field) => <input {...field.field} type="number" placeholder="最大 token 数" style={{ width: '100%' }} />}
        </form.Field>
      </div>
    ),
  },
};
