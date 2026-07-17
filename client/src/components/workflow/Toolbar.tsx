import React, { useCallback, useEffect, useRef, useState } from 'react';
import type { Node, Edge } from 'reactflow';
import { useReactFlow } from 'reactflow';
import {
  Button,
  Input,
  Popover,
  Modal,
  Table,
  Space,
  Tooltip,
  message,
  Popconfirm,
} from 'antd';
import {
  PlayCircleOutlined,
  StopOutlined,
  FullscreenOutlined,
  FullscreenExitOutlined,
  InfoCircleOutlined,
  UnorderedListOutlined,
  LoadingOutlined,
  EditOutlined,
  CheckOutlined,
  CloseOutlined,
  PlusOutlined,
  DeleteOutlined,
  ExportOutlined,
  ImportOutlined,
  LinkOutlined,
  RestOutlined,
  RollbackOutlined,
  CopyOutlined,
  ClockCircleOutlined,
  DatabaseOutlined,
  ApartmentOutlined,
  EyeOutlined,
  EyeInvisibleOutlined,
} from '@ant-design/icons';
import { FlowApi } from './services/FlowApi';
import { listCrons, stopCron } from './nodes/Cron/executor';

/* ───────────────────── Global Variable API ───────────────────── */

const API_BASE =
  (typeof window !== 'undefined' && (window as any).FLASK_BACKEND_URL) || '';

async function listVars() {
  const res = await fetch(`${API_BASE}/api/workflow/vars/list`);
  return res.json();
}
async function setVar(key: string, value: string) {
  const res = await fetch(`${API_BASE}/api/workflow/vars/set`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ key, value }),
  });
  return res.json();
}
async function deleteVar(key: string) {
  const res = await fetch(`${API_BASE}/api/workflow/vars/delete`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ key }),
  });
  return res.json();
}
import type { WorkflowJSON } from './types';

/* ─────────────────────────── helpers ─────────────────────────── */

/** 相对时间：4h 内显示 "x小时y分钟前"，之后显示绝对时间（始终使用本地时间，修正时区偏差）*/
function relativeTime(isoStr?: string): string {
  if (!isoStr) return '';
  // new Date() 会自动按本地时区解析 ISO 字符串，Date.now() 也是本地毫秒数，差值不含时区偏差
  const d = new Date(isoStr);
  if (isNaN(d.getTime())) return '';
  const diff = Date.now() - d.getTime();
  if (diff < 0) return '刚刚'; // 服务器时钟略快时保护
  const mins = Math.floor(diff / 60_000);
  if (mins < 1) return '刚刚';
  if (mins < 60) return `${mins} 分钟前`;
  const hours = Math.floor(mins / 60);
  const remMins = mins % 60;
  if (hours < 4) return remMins > 0 ? `${hours} 小时 ${remMins} 分钟前` : `${hours} 小时前`;
  // 超过 4 小时显示绝对本地时间
  return d.toLocaleString('zh-CN', { hour12: false });
}

/* ─────────────────────────── types ─────────────────────────── */

/** Copy text to clipboard — tries modern API first, falls back to execCommand */
function copyToClipboard(text: string) {
  // Modern async API (preferred, but requires HTTPS)
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text).catch(() => fallbackCopy(text));
    return;
  }
  fallbackCopy(text);
}
function fallbackCopy(text: string) {
  const ta = document.createElement('textarea');
  ta.value = text;
  ta.style.cssText = 'position:fixed;left:-9999px;top:-9999px;opacity:0;pointer-events:none';
  document.body.appendChild(ta);
  ta.focus();
  ta.setSelectionRange(0, ta.value.length);
  try { document.execCommand('copy'); } catch (_) { /* noop */ }
  document.body.removeChild(ta);
}

interface WorkflowRecord {
  id: string;
  name: string;
  author?: string;
  description?: string;
  createdAt?: string;
  updatedAt?: string;
}

export interface ToolbarProps {
  nodes: Node[];
  edges: Edge[];
  setNodes: React.Dispatch<React.SetStateAction<Node[]>>;
  setEdges: React.Dispatch<React.SetStateAction<Edge[]>>;
  workflowId?: string;
  workflowName?: string;
  workflowAuthor?: string;
  workflowDescription?: string;
  workflowCreatedAt?: string;
  workflowUpdatedAt?: string;
  isDirty?: boolean;
  isFullscreen?: boolean;
  onFullscreenToggle?: () => void;
  onSave?: (id: string, name: string) => void;
  onRun?: (json: WorkflowJSON, workflowId?: string) => void;
  runCancelFn?: (() => void) | null;
  /** Called when user picks a workflow from the library to switch to */
  onSwitchWorkflow?: (id: string) => void;
  /** Called when user deletes the current workflow */
  onDeleteWorkflow?: () => void;
  /** If true, auto-open the workflow library modal on mount (driven by URL param) */
  initialLibraryOpen?: boolean;
  /** Compact mode: hide execution result details on nodes */
  compactMode?: boolean;
  /** Toggle compact mode */
  onToggleCompactMode?: () => void;
}

/* ─────────────────────────── component ─────────────────────────── */

const Toolbar: React.FC<ToolbarProps> = ({
  nodes,
  edges,
  setNodes,
  setEdges,
  workflowId,
  workflowName: initialName,
  workflowAuthor: initialAuthor,
  workflowDescription: initialDesc,
  workflowCreatedAt,
  workflowUpdatedAt,
  isDirty = false,
  isFullscreen,
  onFullscreenToggle,
  onSave,
  onRun,
  runCancelFn,
  onSwitchWorkflow,
  onDeleteWorkflow,
  initialLibraryOpen,
  compactMode,
  onToggleCompactMode,
}) => {
  const reactFlowInstance = useReactFlow();
  const isRunning = !!runCancelFn;

  // ── name inline editing ──────────────────────────────────────
  const [name, setName] = useState(initialName || '未命名工作流');
  const [editingName, setEditingName] = useState(false);
  const [nameDraft, setNameDraft] = useState('');
  const nameInputRef = useRef<any>(null);

  // Keep name in sync when parent loads a new workflow
  useEffect(() => { setName(initialName || '未命名工作流'); }, [initialName]);

  const startEditName = () => {
    setNameDraft(name);
    setEditingName(true);
    setTimeout(() => nameInputRef.current?.select(), 50);
  };

  // ── meta info ───────────────────────────────────────────────
  // Must be declared before commitName (used in its useCallback deps)
  const [author, setAuthor] = useState(initialAuthor || '');
  const [description, setDescription] = useState(initialDesc || '');
  useEffect(() => { setAuthor(initialAuthor || ''); }, [initialAuthor]);
  useEffect(() => { setDescription(initialDesc || ''); }, [initialDesc]);

  // ── Auto-save meta info (author / description) on change ─────
  const autoSaveTimerRef = useRef<any>(null);
  const prevMetaRef = useRef({ author: initialAuthor || '', description: initialDesc || '' });

  const doAutoSaveMeta = useCallback(async (authorVal: string, descVal: string) => {
    if (!workflowId) return; // no workflow yet — nothing to save
    setSaving(true);
    try {
      const json = reactFlowInstance.toObject();
      const result = await FlowApi.save(name, json, workflowId, { author: authorVal, description: descVal });
      const now = new Date().toISOString();
      setLastSavedAt(now);
      onSave?.(result.id, name);
    } catch (err: any) {
      message.error(`自动保存失败: ${err.message}`);
    } finally {
      setSaving(false);
    }
  }, [workflowId, name, reactFlowInstance, onSave]);

  useEffect(() => {
    // Skip auto-save during initial sync from parent
    const prev = prevMetaRef.current;
    const changed = (author !== prev.author) || (description !== prev.description);
    prevMetaRef.current = { author, description };
    if (!changed || !workflowId) return;

    if (autoSaveTimerRef.current) clearTimeout(autoSaveTimerRef.current);
    autoSaveTimerRef.current = setTimeout(() => {
      doAutoSaveMeta(author, description);
    }, 800);
    return () => { if (autoSaveTimerRef.current) clearTimeout(autoSaveTimerRef.current); };
  }, [author, description, workflowId, doAutoSaveMeta]);

  // ── Cron management ──────────────────────────────────────────
  const [cronModalOpen, setCronModalOpen] = useState(false);
  const [cronList, setCronList] = useState<any[]>([]);
  const [cronLoading, setCronLoading] = useState(false);

  const refreshCronList = useCallback(async () => {
    setCronLoading(true);
    try {
      const result = await listCrons();
      setCronList(result.crons || []);
    } catch (e: any) {
      message.error('获取定时任务列表失败');
    } finally {
      setCronLoading(false);
    }
  }, []);

  const openCronModal = useCallback(() => {
    setCronModalOpen(true);
    refreshCronList();
  }, [refreshCronList]);

  const handleStopCron = useCallback(async (cronId: string) => {
    try {
      const result = await stopCron(cronId);
      if (result.success) {
        message.success('已停止');
        refreshCronList();
      } else {
        message.error(result.error || '停止失败');
      }
    } catch (e: any) {
      message.error('停止失败');
    }
  }, [refreshCronList]);

  // ── Global Variable management ─────────────────────────────
  const [varModalOpen, setVarModalOpen] = useState(false);
  const [varList, setVarList] = useState<any[]>([]);
  const [varLoading, setVarLoading] = useState(false);
  const [editingVarKey, setEditingVarKey] = useState<string | null>(null);
  const [editingVarValue, setEditingVarValue] = useState('');

  const refreshVarList = useCallback(async () => {
    setVarLoading(true);
    try {
      const result = await listVars();
      setVarList(result.vars || []);
    } catch (e: any) {
      message.error('获取变量列表失败');
    } finally {
      setVarLoading(false);
    }
  }, []);

  const openVarModal = useCallback(() => {
    setVarModalOpen(true);
    refreshVarList();
  }, [refreshVarList]);

  const handleDeleteVar = useCallback(async (key: string) => {
    try {
      const result = await deleteVar(key);
      if (result.success) {
        message.success(`已删除 ${key}`);
        refreshVarList();
      } else {
        message.error(result.error || '删除失败');
      }
    } catch { message.error('删除失败'); }
  }, [refreshVarList]);

  const handleSaveVar = useCallback(async (key: string, value: string) => {
    try {
      const result = await setVar(key, value);
      if (result.success) {
        message.success(`已更新 ${key}`);
        setEditingVarKey(null);
        refreshVarList();
      } else {
        message.error(result.error || '更新失败');
      }
    } catch { message.error('更新失败'); }
  }, [refreshVarList]);

  // ── Add new variable ──────────────────────────────────────────
  const [addVarOpen, setAddVarOpen] = useState(false);
  const [addVarKey, setAddVarKey] = useState('');
  const [addVarValue, setAddVarValue] = useState('');
  const [addVarLoading, setAddVarLoading] = useState(false);

  const openAddVar = () => { setAddVarKey(''); setAddVarValue(''); setAddVarOpen(true); };

  const handleAddVar = async () => {
    const key = addVarKey.trim();
    if (!key) { message.warning('Key 不能为空'); return; }
    if (varList.some(v => v.key === key)) { message.warning(`Key "${key}" 已存在`); return; }
    setAddVarLoading(true);
    try {
      const result = await setVar(key, addVarValue);
      if (result.success) {
        message.success(`已添加 ${key}`);
        setAddVarOpen(false);
        refreshVarList();
      } else {
        message.error(result.error || '添加失败');
      }
    } catch { message.error('添加失败'); }
    finally { setAddVarLoading(false); }
  };

  // commitName: validate → update name → auto-save
  const commitName = useCallback(async () => {
    const trimmed = nameDraft.trim();
    if (!trimmed || trimmed === name) {
      setEditingName(false);
      return;
    }
    // Server-side authoritative name conflict check
    try {
      const exists = await FlowApi.checkName(trimmed, workflowId);
      if (exists) {
        message.error(`「${trimmed}」已存在，请使用其他名称`);
        return; // keep editing
      }
    } catch (_) {
      // If check fails, still allow save
    }
    setName(trimmed);
    setEditingName(false);
    // Trigger save with new name immediately
    setSaving(true);
    try {
      const json = reactFlowInstance.toObject();
      const result = await FlowApi.save(trimmed, json, workflowId, { author, description });
      const now = new Date().toISOString();
      setLastSavedAt(now);
      onSave?.(result.id, trimmed);
      message.success('已重命名并保存');
    } catch (err: any) {
      message.error(`保存失败: ${err.message}`);
    } finally {
      setSaving(false);
    }
  }, [nameDraft, name, workflowId, author, description, reactFlowInstance, onSave]);

  const cancelEditName = () => { setEditingName(false); };

  // ── save ────────────────────────────────────────────────────
  const [saving, setSaving] = useState(false);
  const [lastSavedAt, setLastSavedAt] = useState<string | undefined>(workflowUpdatedAt);
  const [tick, setTick] = useState(0); // force re-render for relative time

  useEffect(() => { setLastSavedAt(workflowUpdatedAt); }, [workflowUpdatedAt]);

  // Refresh relative time display every 30 s
  useEffect(() => {
    const t = setInterval(() => setTick((n) => n + 1), 30_000);
    return () => clearInterval(t);
  }, []);

  const handleSave = useCallback(async (nameOverride?: string) => {
    setSaving(true);
    const saveName = nameOverride ?? name;
    try {
      const json = reactFlowInstance.toObject();
      const result = await FlowApi.save(saveName, json, workflowId, { author, description });
      const now = new Date().toISOString();
      setLastSavedAt(now);
      onSave?.(result.id, saveName);
      message.success('保存成功');
    } catch (err: any) {
      message.error(`保存失败: ${err.message}`);
    } finally {
      setSaving(false);
    }
  }, [name, author, description, workflowId, reactFlowInstance, onSave]);

  // ── run / stop ──────────────────────────────────────────────
  const handleRun = async () => {
    if (!workflowId) { message.warning('请先保存工作流'); return; }
    const json = reactFlowInstance.toObject();
    onRun?.(json, workflowId);
  };
  const handleStop = () => { runCancelFn?.(); message.info('已请求停止运行'); };

  // ── import / export ─────────────────────────────────────────
  const handleExport = () => {
    const json = reactFlowInstance.toObject();
    const blob = new Blob([JSON.stringify(json, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = `${name}.json`; a.click();
    URL.revokeObjectURL(url);
  };
  const handleImport = () => {
    const input = document.createElement('input');
    input.type = 'file'; input.accept = '.json';
    input.onchange = (e: any) => {
      const file = e.target.files?.[0]; if (!file) return;
      const reader = new FileReader();
      reader.onload = (ev) => {
        try {
          const json = JSON.parse(ev.target?.result as string);
          if (json.nodes) setNodes(json.nodes as Node[]);
          if (json.edges) setEdges(json.edges as Edge[]);
          if (json.viewport) reactFlowInstance.setViewport(json.viewport);
          message.success('导入成功');
        } catch { message.error('JSON 解析失败'); }
      };
      reader.readAsText(file);
    };
    input.click();
  };

  // ── workflow library modal ───────────────────────────────────
  const [libraryOpen, setLibraryOpen] = useState(!!initialLibraryOpen);
  const [libraryLoading, setLibraryLoading] = useState(false);
  const [libraryData, setLibraryData] = useState<WorkflowRecord[]>([]);
  const [librarySearch, setLibrarySearch] = useState('');

  const fetchLibrary = async () => {
    setLibraryLoading(true);
    try {
      const result = await FlowApi.list();
      setLibraryData(result.list || []);
    } catch (err: any) {
      message.error(`加载失败: ${err.message}`);
    } finally {
      setLibraryLoading(false);
    }
  };

  const openLibrary = () => { setLibraryOpen(true); fetchLibrary(); };

  // Auto-open library from URL param on mount
  useEffect(() => {
    if (initialLibraryOpen) { fetchLibrary(); }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Sync library_open URL param
  useEffect(() => {
    const url = new URL(window.location.href);
    if (libraryOpen) {
      url.searchParams.set('library_open', 'true');
    } else {
      url.searchParams.delete('library_open');
    }
    const next = url.pathname + url.search;
    if (next !== window.location.pathname + window.location.search) {
      window.history.replaceState(null, '', next);
    }
  }, [libraryOpen]);

  const handleDeleteWorkflow = async (id: string) => {
    try {
      await FlowApi.delete(id);
      message.success('已移入垃圾箱');
      fetchLibrary();
    } catch (err: any) {
      message.error(`删除失败: ${err.message}`);
    }
  };

  // ── Duplicate ────────────────────────────────────────────────
  const [dupTarget, setDupTarget] = useState<WorkflowRecord | null>(null);
  const [dupName, setDupName] = useState('');
  const [dupLoading, setDupLoading] = useState(false);

  const openDup = (record: WorkflowRecord) => {
    setDupTarget(record);
    setDupName(`${record.name}_副本`);
  };

  const handleDuplicate = async () => {
    if (!dupTarget || !dupName.trim()) return;
    setDupLoading(true);
    try {
      await FlowApi.duplicateWorkflow(dupTarget.id, dupName.trim());
      message.success(`已复制为「${dupName.trim()}」`);
      setDupTarget(null);
      fetchLibrary();
    } catch (err: any) {
      message.error(`复制失败: ${err.message}`);
    } finally {
      setDupLoading(false);
    }
  };

  // ── new workflow naming modal ────────────────────────────────
  const [newNameOpen, setNewNameOpen] = useState(false);
  const [newNameDraft, setNewNameDraft] = useState('');
  const [newNameLoading, setNewNameLoading] = useState(false);
  const [newNameError, setNewNameError] = useState('');
  const newNameInputRef = useRef<Input>(null);

  const openNewWorkflow = () => {
    setNewNameDraft('');
    setNewNameError('');
    setNewNameOpen(true);
  };

  const handleCreateNew = async () => {
    const trimmed = newNameDraft.trim();
    if (!trimmed) { setNewNameError('请输入工作流名称'); return; }
    setNewNameLoading(true);
    try {
      // Server-side authoritative check to handle concurrent creation
      const exists = await FlowApi.checkName(trimmed);
      if (exists) {
        setNewNameError(`「${trimmed}」已存在，请使用其他名称`);
        setNewNameLoading(false);
        return;
      }
      // Save empty workflow to server immediately
      const result = await FlowApi.save(trimmed, { nodes: [], edges: [] }, undefined, { author: '', description: '' });
      setNewNameLoading(false);
      setNewNameOpen(false);
      setLibraryOpen(false);
      // Navigate to the newly created workflow by its server-assigned id
      if (result?.id) {
        onSwitchWorkflow?.(result.id);
      } else {
        onSwitchWorkflow?.(`__new__:${trimmed}`);
      }
    } catch (err: any) {
      setNewNameError(`创建失败: ${err.message}`);
      setNewNameLoading(false);
    }
  };
  const [trashOpen, setTrashOpen] = useState(false);
  const [trashLoading, setTrashLoading] = useState(false);
  const [trashData, setTrashData] = useState<any[]>([]);

  const fetchTrash = async () => {
    setTrashLoading(true);
    try {
      const list = await FlowApi.listTrash();
      setTrashData(list);
    } catch (err: any) {
      message.error(`加载垃圾箱失败: ${err.message}`);
    } finally {
      setTrashLoading(false);
    }
  };

  const handleRestore = async (id: string) => {
    try {
      await FlowApi.restoreFromTrash(id);
      message.success('还原成功');
      fetchTrash();
      fetchLibrary();
    } catch (err: any) {
      message.error(`还原失败: ${err.message}`);
    }
  };

  const handlePurge = async (id: string) => {
    try {
      await FlowApi.purgeFromTrash(id);
      message.success('已彻底删除');
      fetchTrash();
    } catch (err: any) {
      message.error(`删除失败: ${err.message}`);
    }
  };

  // ── Auto Layout ─────────────────────────────────────────────
  const handleAutoLayout = useCallback(() => {
    if (nodes.length === 0) return;

    // 1. Build adjacency from edges
    const inDegree: Record<string, number> = {};
    const outEdges: Record<string, string[]> = {};  // nodeId → downstream nodeIds
    const nodeMap: Record<string, Node> = {};
    for (const n of nodes) { nodeMap[n.id] = n; inDegree[n.id] = 0; outEdges[n.id] = []; }
    for (const e of edges) {
      if (nodeMap[e.source] && nodeMap[e.target]) {
        outEdges[e.source].push(e.target);
        inDegree[e.target] = (inDegree[e.target] || 0) + 1;
      }
    }

    // 2. Topological sort → assign levels (BFS Kahn's algorithm)
    const levels: Record<string, number> = {};
    const queue: string[] = [];
    for (const id of Object.keys(inDegree)) {
      if (inDegree[id] === 0) queue.push(id);
    }
    while (queue.length > 0) {
      const id = queue.shift()!;
      const parentLevel = levels[id] ?? 0;
      for (const child of outEdges[id]) {
        const childLevel = Math.max(levels[child] ?? 0, parentLevel + 1);
        levels[child] = childLevel;
        inDegree[child]--;
        if (inDegree[child] === 0) queue.push(child);
      }
    }
    // Handle cycles: unvisited nodes get level 0
    for (const id of Object.keys(nodeMap)) {
      if (levels[id] === undefined) levels[id] = 0;
    }

    // 3. Group nodes by level
    const levelGroups: Record<number, string[]> = {};
    for (const [id, lv] of Object.entries(levels)) {
      if (!levelGroups[lv]) levelGroups[lv] = [];
      levelGroups[lv].push(id);
    }

    // 4. Compute node sizes (use actual width/height if available, else defaults)
    const DEFAULT_W = 220;
    const DEFAULT_H = 180;
    const getNodeSize = (node: Node): { w: number; h: number } => {
      const measured_w = node.width || node.measured?.width || DEFAULT_W;
      // For executed nodes, use measured height which includes output preview
      const data = node.data as Record<string, any>;
      const hasOutput = data?._runStatusHint && data._runStatusHint !== 'idle';
      const measured_h = node.height || node.measured?.height || DEFAULT_H;
      const h = hasOutput ? Math.max(measured_h, 280) : Math.max(measured_h, DEFAULT_H);
      return { w: Math.max(measured_w, DEFAULT_W), h };
    };

    // 5. Layout: left-to-right, each level is a column
    const COL_GAP = 80;    // horizontal gap between columns
    const ROW_GAP = 24;    // vertical gap between nodes in same column
    const START_X = 50;
    const START_Y = 50;

    const newPositions: Record<string, { x: number; y: number }> = {};

    const sortedLevels = Object.keys(levelGroups).map(Number).sort((a, b) => a - b);
    let currentX = START_X;

    for (const lv of sortedLevels) {
      const ids = levelGroups[lv];
      // Compute sizes for this level
      const sizes: Record<string, { w: number; h: number }> = {};
      let colWidth = 0;
      for (const id of ids) {
        sizes[id] = getNodeSize(nodeMap[id]);
        colWidth = Math.max(colWidth, sizes[id].w);
      }

      // Stack nodes vertically in this column
      let currentY = START_Y;
      for (const id of ids) {
        newPositions[id] = { x: currentX, y: currentY };
        currentY += sizes[id].h + ROW_GAP;
      }

      currentX += colWidth + COL_GAP;
    }

    // 6. Apply new positions with smooth animation
    setNodes((prev) =>
      prev.map((n) => {
        const pos = newPositions[n.id];
        return pos ? { ...n, position: pos } : n;
      })
    );

    // 7. Fit viewport to show all nodes
    setTimeout(() => {
      reactFlowInstance.fitView({ padding: 0.15, duration: 400 });
    }, 50);

    message.success('节点布局已自动整理');
  }, [nodes, edges, setNodes, reactFlowInstance]);

  const handleSwitchTo = (targetId: string) => {
    if (targetId === workflowId) { setLibraryOpen(false); return; }
    const doSwitch = () => { setLibraryOpen(false); onSwitchWorkflow?.(targetId); };
    if (isDirty) {
      Modal.confirm({
        title: '当前工作流未保存',
        content: '是否先保存当前工作流再切换？',
        okText: '保存并切换',
        cancelText: '直接切换',
        onOk: async () => { await handleSave(); doSwitch(); },
        onCancel: doSwitch,
      });
    } else {
      doSwitch();
    }
  };

  /** Format workflow label: name(desc) with max desc length */
  const formatWorkflowLabel = (name: string, desc?: string, maxDesc = 20) => {
    if (!desc || !desc.trim()) return name;
    const d = desc.trim().length > maxDesc ? desc.trim().slice(0, maxDesc) + '…' : desc.trim();
    return `${name}(${d})`;
  };

  const libraryColumns = [
    {
      title: '名称', dataIndex: 'name', key: 'name', ellipsis: true,
      render: (v: string, r: WorkflowRecord) => {
        const label = formatWorkflowLabel(v, r.description);
        const base = window.location.pathname.includes('fullscreen')
          ? '/workflow/fullscreen'
          : '/workflow/editor';
        const href = `${base}?id=${r.id}`;
        return (
          <a
            href={href}
            style={{
              fontWeight: r.id === workflowId ? 600 : 400,
              color: '#1890ff',
              textDecoration: 'underline',
              textUnderlineOffset: 2,
              cursor: 'pointer',
            }}
            onClick={(e) => {
              if (e.ctrlKey || e.metaKey) return; // 浏览器原生处理新开标签页
              e.preventDefault();
              handleSwitchTo(r.id);
            }}
          >
            {label}{r.id === workflowId ? ' （当前）' : ''}
          </a>
        );
      },
    },
    { title: '作者', dataIndex: 'author', key: 'author', width: 90, render: (v: string) => v || '-' },
    {
      title: '创建时间', dataIndex: 'createdAt', key: 'createdAt', width: 155,
      render: (v: string) => v ? new Date(v).toLocaleString('zh-CN') : '-',
    },
    {
      title: '最后更新', dataIndex: 'updatedAt', key: 'updatedAt', width: 155,
      render: (v: string) => v ? new Date(v).toLocaleString('zh-CN') : '-',
      // No defaultSortOrder — we control order via dataSource preprocessing
      // to ensure current workflow is always on the first page
      sorter: (a: WorkflowRecord, b: WorkflowRecord) => {
        if (a.id === workflowId) return -1;
        if (b.id === workflowId) return 1;
        return (b.updatedAt || '').localeCompare(a.updatedAt || '');
      },
    },
    {
      title: '操作', key: 'action', width: 90,
      render: (_: any, record: WorkflowRecord) => (
        <Space size={4}>
          <Tooltip title="复制">
            <Button
              size="small"
              icon={<CopyOutlined />}
              onClick={() => openDup(record)}
            />
          </Tooltip>
          <Popconfirm title="确认删除？" onConfirm={() => handleDeleteWorkflow(record.id)} okText="删除" cancelText="取消">
            <Button size="small" danger icon={<DeleteOutlined />} disabled={record.id === workflowId} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  // ── meta info popover ────────────────────────────────────────
  const formatTime = (t?: string) => t ? new Date(t).toLocaleString('zh-CN') : '-';
  const metaContent = (
    <div style={{ width: 280 }}>
      <div style={{ marginBottom: 8 }}>
        <label style={{ display: 'block', fontSize: 11, color: '#888', marginBottom: 2 }}>作者</label>
        <Input value={author} onChange={(e) => setAuthor(e.target.value)} size="small" placeholder="可选" />
      </div>
      <div style={{ marginBottom: 8 }}>
        <label style={{ display: 'block', fontSize: 11, color: '#888', marginBottom: 2 }}>描述</label>
        <Input.TextArea value={description} onChange={(e) => setDescription(e.target.value)} size="small" rows={2} placeholder="可选" />
      </div>
      <div style={{ fontSize: 11, color: '#999' }}>
        <div>创建时间: {formatTime(workflowCreatedAt)}</div>
        <div>最后保存: {formatTime(lastSavedAt)}</div>
      </div>
    </div>
  );

  const savedLabel = ((_tick) => {
    if (isDirty) return <span style={{ color: '#ffc53d', fontSize: 12 }}>未保存</span>;
    if (!lastSavedAt) return null;
    return <span style={{ color: 'rgba(255,255,255,0.45)', fontSize: 12 }}>已保存 {relativeTime(lastSavedAt)}</span>;
  })(tick);

  return (
    <div style={{
      height: 48,
      borderBottom: '1px solid #1d2a3a',
      display: 'flex',
      alignItems: 'center',
      padding: '0 12px',
      background: '#1f2f3f',
      gap: 0,
      flexShrink: 0,
      position: 'relative',
    }}>
      {/* ── 左区：工作流名称 + 保存状态 ── */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0, maxWidth: 480 }}>
        {editingName ? (
          <Input
            ref={nameInputRef}
            value={nameDraft}
            onChange={(e) => setNameDraft(e.target.value)}
            onPressEnter={() => nameInputRef.current?.blur()}
            onBlur={() => commitName()}
            onKeyDown={(e) => e.key === 'Escape' && cancelEditName()}
            size="small"
            style={{ fontSize: 14, fontWeight: 600, minWidth: 160, width: `${Math.max(nameDraft.length * 9, 160)}px` }}
          />
        ) : (
          <Tooltip title="点击编辑名称">
            <span
              onClick={startEditName}
              style={{
                fontSize: 14, fontWeight: 600, cursor: 'pointer',
                whiteSpace: 'nowrap',
                color: '#e8edf2',
                padding: '2px 4px', borderRadius: 4,
                transition: 'background 0.15s',
              }}
              onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(255,255,255,0.1)')}
              onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
            >
              {name}
              <EditOutlined style={{ fontSize: 11, marginLeft: 4, color: 'rgba(255,255,255,0.3)' }} />
            </span>
          </Tooltip>
        )}
        <div style={{ flexShrink: 0 }}>{savedLabel}</div>
      </div>

      <div style={{ width: 1, height: 24, background: 'rgba(255,255,255,0.15)', margin: '0 10px' }} />

      {/* ── 中左区：信息 + 简略/详细 + 运行/停止 ── */}
      <Space size={8}>
        <Popover content={metaContent} title="工作流信息" trigger="click">
          <Button icon={<InfoCircleOutlined />} size="small">信息</Button>
        </Popover>
        <Tooltip title={compactMode ? '当前：简略模式（仅显示入参）' : '当前：详细模式（显示执行结果）'}>
          <Button
            icon={compactMode ? <EyeInvisibleOutlined /> : <EyeOutlined />}
            size="small"
            type={compactMode ? 'primary' : 'default'}
            onClick={onToggleCompactMode}
          >
            {compactMode ? '简略' : '详细'}
          </Button>
        </Tooltip>
        {isRunning ? (
          <Button
            icon={<StopOutlined />}
            size="small" danger
            onClick={handleStop}
          >
            停止
          </Button>
        ) : (
          <Button
            type="primary"
            icon={saving ? <LoadingOutlined /> : <PlayCircleOutlined />}
            size="small"
            disabled={saving}
            onClick={handleRun}
          >
            运行
          </Button>
        )}
        <Button
          icon={saving ? <LoadingOutlined /> : undefined}
          size="small"
          loading={saving}
          onClick={() => handleSave()}
        >
          保存
        </Button>
        
      <div style={{ width: 1, height: 24, background: 'rgba(255,255,255,0.15)', margin: '0 10px' }} />

          <Tooltip title="自动整理节点布局">
          <Button size="small" icon={<ApartmentOutlined />} onClick={handleAutoLayout}>整理</Button>
        </Tooltip>
        {workflowId && (
          <Popconfirm
            title="确定删除当前工作流？"
            description="删除后将移入垃圾箱，并打开工作流库"
            onConfirm={async () => {
              try {
                await FlowApi.delete(workflowId);
                message.success('已移入垃圾箱');
                onDeleteWorkflow?.();
              } catch (e: any) {
                message.error(`删除失败: ${e.message}`);
              }
            }}
            okText="删除"
            cancelText="取消"
            okButtonProps={{ danger: true }}
          >
            <Button size="small" danger icon={<DeleteOutlined />}>删除</Button>
          </Popconfirm>
        )}
      </Space>

      {/* ── 中区：工作流库（绝对定位，基于整个 toolbar 居中）── */}
      <div style={{ position: 'absolute', left: '50%', transform: 'translateX(-50%)' }}>
        <Button
          icon={<UnorderedListOutlined />}
          size="small"
          onClick={openLibrary}
          style={{ minWidth: 100 }}
        >
          工作流库
        </Button>
      </div>

      <div style={{ width: 1, height: 24, background: 'rgba(255,255,255,0.15)', margin: '0 10px' }} />

      {/* ── 推右区到最右 */}
      <div style={{ marginLeft: 'auto' }} />

      {/* ── 右区：导入/导出 + 变量管理 + 定时任务 + 全屏 ── */}
      <Space size={4}>
        <Tooltip title="全局变量管理">
          <Button icon={<DatabaseOutlined />} size="small" onClick={openVarModal}>变量管理</Button>
        </Tooltip>
        <Tooltip title="定时任务管理">
          <Button icon={<ClockCircleOutlined />} size="small" onClick={openCronModal}>定时任务</Button>
        </Tooltip>
        <Tooltip title="导入 JSON">
          <Button icon={<ImportOutlined />} size="small" onClick={handleImport} />
        </Tooltip>
        <Tooltip title="导出 JSON">
          <Button icon={<ExportOutlined />} size="small" onClick={handleExport} />
        </Tooltip>
        <Button
          icon={isFullscreen ? <FullscreenExitOutlined /> : <FullscreenOutlined />}
          onClick={onFullscreenToggle}
          size="small"
          type={isFullscreen ? 'primary' : 'default'}
        >
          {isFullscreen ? '退出全屏' : '全屏'}
        </Button>
      </Space>

      {/* ── 全局变量管理 Modal ── */}
      <Modal
        title={<span style={{ color: '#1f2f3f', fontWeight: 700, fontSize: 15 }}>📦 全局变量管理</span>}
        open={varModalOpen}
        onCancel={() => { setVarModalOpen(false); setEditingVarKey(null); }}
        footer={
          <Space>
            <Button size="small" type="primary" icon={<PlusOutlined />} onClick={openAddVar}>新增</Button>
            <Button size="small" onClick={refreshVarList} loading={varLoading}>刷新</Button>
          </Space>
        }
        width={900}
        destroyOnHidden
        styles={{ body: { padding: '12px 8px' } }}
      >
        <Table
          dataSource={varList}
          rowKey="key"
          size="small"
          pagination={false}
          loading={varLoading}
          locale={{ emptyText: '暂无全局变量' }}
          columns={[
            {
              title: 'Key', dataIndex: 'key', width: 180, ellipsis: true,
              render: (v: string) => v,
            },
            {
              title: '当前值', dataIndex: 'value', width: 300,
              render: (v: string, r: any) =>
                editingVarKey === r.key ? (
                  <Space size={4}>
                    <Input
                      size="small"
                      value={editingVarValue}
                      onChange={e => setEditingVarValue(e.target.value)}
                      onPressEnter={() => handleSaveVar(r.key, editingVarValue)}
                      onKeyDown={e => { if (e.key === 'Escape') setEditingVarKey(null); }}
                      autoFocus
                      style={{ flex: 1, minWidth: 120 }}
                    />
                    <CheckOutlined style={{ color: '#52c41a', cursor: 'pointer', fontSize: 14 }} onClick={() => handleSaveVar(r.key, editingVarValue)} />
                    <CloseOutlined style={{ color: '#999', cursor: 'pointer', fontSize: 14 }} onClick={() => setEditingVarKey(null)} />
                  </Space>
                ) : (
                  <Space size={4}>
                    <span style={{ cursor: 'default' }}>{v ?? '(空)'}</span>
                    <EditOutlined style={{ color: '#999', cursor: 'pointer', fontSize: 11 }} onClick={() => { setEditingVarKey(r.key); setEditingVarValue(v ?? ''); }} />
                  </Space>
                ),
            },
            { title: '更新时间', dataIndex: 'updated_at', width: 150, render: (v: string) => v ? relativeTime(v) : '-' },
            {
              title: '操作', width: 70,
              render: (_: any, r: any) => (
                <Popconfirm title={`确定删除变量 "${r.key}" ？`} onConfirm={() => handleDeleteVar(r.key)} okText="删除" cancelText="取消">
                  <Button size="small" danger icon={<DeleteOutlined />}>删除</Button>
                </Popconfirm>
              ),
            },
          ]}
        />
      </Modal>

      {/* ── 新增全局变量 Modal ── */}
      <Modal
        title={<span style={{ color: '#1f2f3f', fontWeight: 700, fontSize: 15 }}>➕ 新增全局变量</span>}
        open={addVarOpen}
        onCancel={() => setAddVarOpen(false)}
        onOk={handleAddVar}
        okText="确认"
        cancelText="取消"
        confirmLoading={addVarLoading}
        width={420}
        destroyOnHidden
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginTop: 8 }}>
          <div>
            <div style={{ marginBottom: 4, fontWeight: 600 }}>Key</div>
            <Input
              size="small"
              value={addVarKey}
              onChange={e => setAddVarKey(e.target.value)}
              onPressEnter={handleAddVar}
              placeholder="变量名"
              autoFocus
            />
          </div>
          <div>
            <div style={{ marginBottom: 4, fontWeight: 600 }}>Value</div>
            <Input
              size="small"
              value={addVarValue}
              onChange={e => setAddVarValue(e.target.value)}
              onPressEnter={handleAddVar}
              placeholder="变量值"
            />
          </div>
        </div>
      </Modal>

      {/* ── 定时任务管理 Modal ── */}
      <Modal
        title={<span style={{ color: '#1f2f3f', fontWeight: 700, fontSize: 15 }}>⏰ 定时任务管理</span>}
        open={cronModalOpen}
        onCancel={() => setCronModalOpen(false)}
        footer={<Button size="small" onClick={refreshCronList} loading={cronLoading}>刷新</Button>}
        width={900}
        destroyOnHidden
        styles={{ body: { padding: '12px 8px' } }}
      >
        <Table
          dataSource={cronList}
          rowKey="cron_id"
          size="small"
          pagination={false}
          loading={cronLoading}
          locale={{ emptyText: '暂无运行中的定时任务' }}
          columns={[
            { title: 'ID', dataIndex: 'cron_id', width: 110, ellipsis: true },
            { title: 'Cron 表达式', dataIndex: 'cron_expr', width: 120 },
            { title: '状态', dataIndex: 'status', width: 80, render: (v: string) => (
              <span style={{ color: v === 'running' ? '#52c41a' : '#999', fontWeight: 600 }}>
                {v === 'running' ? '🟢 运行中' : v === 'stopping' ? '⏹ 停止中' : '⚪ 已停止'}
              </span>
            )},
            { title: '已执行', dataIndex: 'run_count', width: 60, align: 'center' as const },
            { title: '上次执行', dataIndex: 'last_run', width: 130, render: (v: string) => v ? relativeTime(v) : '-' },
            { title: '启动时间', dataIndex: 'started_at', width: 130, render: (v: string) => relativeTime(v) },
            { title: '操作', width: 70, render: (_: any, r: any) => (
              r.status === 'running' ? (
                <Popconfirm title="确定停止该定时任务？" onConfirm={() => handleStopCron(r.cron_id)} okText="停止" cancelText="取消">
                  <Button size="small" danger icon={<StopOutlined />}>停止</Button>
                </Popconfirm>
              ) : <span style={{ color: '#999', fontSize: 11 }}>已停止</span>
            )},
          ]}
        />
      </Modal>

      {/* ── 工作流库 Modal ── */}
      <Modal
        title={
          <span style={{ color: '#1f2f3f', fontWeight: 700, fontSize: 15 }}>
            🗂️ 工作流库
          </span>
        }
        open={libraryOpen}
        onCancel={() => { setLibraryOpen(false); setLibrarySearch(''); }}
        footer={
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <Space>
              <Button
                type="primary"
                icon={<PlusOutlined />}
                onClick={openNewWorkflow}
              >
                新建工作流
              </Button>
              <Button
                icon={<RestOutlined />}
                onClick={() => { setTrashOpen(true); fetchTrash(); }}
              >
                垃圾箱
              </Button>
            </Space>
            <Button onClick={() => { setLibraryOpen(false); setLibrarySearch(''); }}>关闭</Button>
          </div>
        }
        width={900}
        destroyOnHidden
        styles={{ body: { background: '#f0f4f8', padding: '16px 16px 8px' } }}
      >
        <Input.Search
          placeholder="搜索工作流名称、作者..."
          allowClear
          value={librarySearch}
          onChange={(e) => setLibrarySearch(e.target.value)}
          style={{ marginBottom: 12 }}
        />
        <Table
          columns={libraryColumns}
          dataSource={(() => {
            const filtered = libraryData.filter((r) => {
              if (!librarySearch.trim()) return true;
              const q = librarySearch.toLowerCase();
              return (
                (r.name || '').toLowerCase().includes(q) ||
                (r.author || '').toLowerCase().includes(q) ||
                (r.description || '').toLowerCase().includes(q)
              );
            });
            // Split: current workflow first, then rest sorted by updatedAt desc
            const current = filtered.find((r) => r.id === workflowId);
            const rest = filtered.filter((r) => r.id !== workflowId)
              .sort((a, b) => ((b.updatedAt || '') as string).localeCompare((a.updatedAt || '') as string));
            return current ? [current, ...rest] : rest;
          })()}
          rowKey="id"
          loading={libraryLoading}
          size="small"
          pagination={{ pageSize: 8, showSizeChanger: false }}
          rowClassName={(r) => r.id === workflowId ? 'workflow-lib-active-row' : ''}
        />
      </Modal>

      {/* ── 垃圾箱 Modal ── */}
      <Modal
        title={
          <span style={{ color: '#1f2f3f', fontWeight: 700, fontSize: 15 }}>
            🗑️ 垃圾箱
          </span>
        }
        open={trashOpen}
        onCancel={() => setTrashOpen(false)}
        footer={<Button onClick={() => setTrashOpen(false)}>关闭</Button>}
        width={680}
        destroyOnHidden
        styles={{ body: { background: '#fff7f0', padding: '16px 16px 8px' } }}
      >
        <Table
          dataSource={trashData}
          rowKey="id"
          loading={trashLoading}
          size="small"
          pagination={{ pageSize: 8, showSizeChanger: false }}
          locale={{ emptyText: '垃圾箱是空的' }}
          columns={[
            {
              title: '名称', dataIndex: 'name', key: 'name', ellipsis: true,
              render: (v: string) => <span style={{ color: '#595959' }}>{v}</span>,
            },
            { title: '作者', dataIndex: 'author', key: 'author', width: 90, render: (v: string) => v || '-' },
            {
              title: '删除时间', dataIndex: 'deletedAt', key: 'deletedAt', width: 155,
              render: (v: string) => v ? new Date(v).toLocaleString('zh-CN') : '-',
              defaultSortOrder: 'descend' as const,
              sorter: (a: any, b: any) => (a.deletedAt || '').localeCompare(b.deletedAt || ''),
            },
            {
              title: '操作', key: 'action', width: 120,
              render: (_: any, record: any) => (
                <Space size={4}>
                  <Tooltip title="还原到工作流库">
                    <Button
                      size="small"
                      icon={<RollbackOutlined />}
                      onClick={() => handleRestore(record.id)}
                    >
                      还原
                    </Button>
                  </Tooltip>
                  <Popconfirm
                    title="彻底删除后无法恢复，确认吗？"
                    onConfirm={() => handlePurge(record.id)}
                    okText="彻底删除"
                    cancelText="取消"
                    okButtonProps={{ danger: true }}
                  >
                    <Button size="small" danger icon={<DeleteOutlined />} />
                  </Popconfirm>
                </Space>
              ),
            },
          ]}
        />
      </Modal>
      {/* ── 新建工作流命名 Modal ── */}
      <Modal
        title={<span style={{ fontWeight: 700 }}>新建工作流</span>}
        open={newNameOpen}
        onCancel={() => setNewNameOpen(false)}
        onOk={handleCreateNew}
        okText="创建"
        cancelText="取消"
        confirmLoading={newNameLoading}
        width={400}
        destroyOnHidden
        afterOpenChange={(visible) => {
          if (visible) {
            // destroyOnHidden makes autoFocus unreliable;
            // use ref to explicitly focus after modal animation completes
            setTimeout(() => {
              newNameInputRef.current?.focus({ cursor: 'all' });
            }, 100);
          }
        }}
      >
        <div style={{ marginBottom: 6, fontSize: 13, color: '#595959' }}>工作流名称</div>
        <Input
          ref={newNameInputRef}
          value={newNameDraft}
          onChange={(e) => { setNewNameDraft(e.target.value); setNewNameError(''); }}
          onPressEnter={handleCreateNew}
          placeholder="请输入新工作流名称"
          maxLength={80}
          showCount
          status={newNameError ? 'error' : undefined}
        />
        {newNameError && (
          <div style={{ color: '#ff4d4f', fontSize: 12, marginTop: 4 }}>{newNameError}</div>
        )}
      </Modal>

      {/* ── 复制工作流 Modal ── */}
      <Modal
        title={<span style={{ fontWeight: 700 }}>复制工作流</span>}
        open={!!dupTarget}
        onCancel={() => setDupTarget(null)}
        onOk={handleDuplicate}
        okText="确认复制"
        cancelText="取消"
        confirmLoading={dupLoading}
        width={420}
        destroyOnHidden
      >
        <div style={{ marginBottom: 8, color: '#595959', fontSize: 13 }}>
          来源：<strong>{dupTarget?.name}</strong>
        </div>
        <div style={{ marginBottom: 6, fontSize: 13, color: '#595959' }}>新工作流名称</div>
        <Input
          value={dupName}
          onChange={(e) => setDupName(e.target.value)}
          onPressEnter={handleDuplicate}
          placeholder="请输入新名称"
          autoFocus
          maxLength={80}
          showCount
        />
      </Modal>
    </div>
  );
};

export default Toolbar;
