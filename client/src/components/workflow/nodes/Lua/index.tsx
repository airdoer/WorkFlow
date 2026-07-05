import React from 'react';
import { FlowNodeRegistry, ValidateTrigger } from '@flowgram.ai/free-layout-editor';

export const LuaNodeRegistry: FlowNodeRegistry = {
  type: 'lua',
  meta: {
    title: 'Lua',
    defaultPorts: [{ type: 'output' }, { type: 'input' }],
  },
  formMeta: {
    validateTrigger: ValidateTrigger.onChange,
    validate: {
      p4Path: ({ value }) => (value ? undefined : 'P4 路径必填'),
    },
    render: ({ form }) => (
      <div>
        <form.Field name="p4Path">
          {(field) => <input {...field.field} placeholder="P4 文件路径" style={{ width: '100%', marginBottom: 8 }} />}
        </form.Field>
        <form.Field name="entryFunction">
          {(field) => <input {...field.field} placeholder="入口函数名（可选）" style={{ width: '100%' }} />}
        </form.Field>
      </div>
    ),
  },
};
