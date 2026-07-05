import React from 'react';
import { FlowNodeRegistry, ValidateTrigger } from '@flowgram.ai/free-layout-editor';

export const ExcelNodeRegistry: FlowNodeRegistry = {
  type: 'excel',
  meta: {
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
        <form.Field name="sheet">
          {(field) => <input {...field.field} placeholder="工作表名（可选）" style={{ width: '100%' }} />}
        </form.Field>
      </div>
    ),
  },
};
