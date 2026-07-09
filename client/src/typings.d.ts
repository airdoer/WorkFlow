declare module '*.css';
declare module '*.less';
declare module '*.scss';
declare module '*.sass';
declare module '*.svg';
declare module '*.png';
declare module '*.jpg';
declare module '*.jpeg';
declare module '*.gif';
declare module '*.bmp';
declare module '*.tiff';
declare module '*.md' {
  const content: string;
  export default content;
}
declare module 'mockjs';
declare module 'jsoneditor-react' {
  import { Component } from 'react';
  export class JsonEditor extends Component<any, any> {}
}
declare module 'jsoneditor/dist/jsoneditor-minimalist';
declare module 'jsoneditor/dist/jsoneditor.css';

declare const __APP_VERSION__: string;
declare const __UMI_VERSION__: string;
declare const __UTOO_VERSION__: string;
