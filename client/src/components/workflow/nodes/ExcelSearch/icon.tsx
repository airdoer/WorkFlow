import React from 'react';

export default function ExcelSearchIcon({ size = 14 }: { size?: number }) {
  return (
    <span style={{ fontSize: size, display: 'inline-flex', alignItems: 'center', color: '#52c41a' }}>
      🔍
    </span>
  );
}
