import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Box,
  Button,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  List,
  ListItem,
  ListItemText,
  MenuItem,
  Stack,
  TextField,
  Typography,
} from '@mui/material'
import { api, extractErrorMessage } from '../api/client'
import type { DatabaseConnection, FileRecord, KnowledgeBase } from '../api/types'

const DB_TYPES = ['postgresql', 'mysql', 'sqlserver']

function ConnectionsPanel() {
  const queryClient = useQueryClient()
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState({
    name: '',
    database_type: 'postgresql',
    host: '',
    port: 5432,
    database_name: '',
    username: '',
    password: '',
  })
  const [statusMessage, setStatusMessage] = useState<string | null>(null)

  const { data: connections } = useQuery({
    queryKey: ['connections'],
    queryFn: async () => (await api.get<DatabaseConnection[]>('/database-connections')).data,
  })

  const createMutation = useMutation({
    mutationFn: async () => api.post('/database-connections', form),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['connections'] })
      setOpen(false)
    },
  })

  const testMutation = useMutation({
    mutationFn: async (id: string) => api.post(`/database-connections/${id}/test`),
    onSuccess: (response) => setStatusMessage(response.data.message),
  })

  const syncMutation = useMutation({
    mutationFn: async (id: string) => api.post(`/database-connections/${id}/sync-schema`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['connections'] })
      setStatusMessage('Schema sync triggered.')
    },
  })

  return (
    <Box>
      <Stack direction="row" justifyContent="space-between" alignItems="center" mb={1}>
        <Typography variant="h6">Database connections</Typography>
        <Button size="small" onClick={() => setOpen(true)}>
          + New connection
        </Button>
      </Stack>
      {statusMessage && (
        <Typography variant="body2" color="text.secondary" mb={1}>
          {statusMessage}
        </Typography>
      )}
      <List dense>
        {connections?.map((c) => (
          <ListItem
            key={c.id}
            secondaryAction={
              <Stack direction="row" spacing={1}>
                <Button size="small" onClick={() => testMutation.mutate(c.id)}>
                  Test
                </Button>
                <Button size="small" onClick={() => syncMutation.mutate(c.id)}>
                  Sync schema
                </Button>
              </Stack>
            }
          >
            <ListItemText
              primary={`${c.name} (${c.database_type})`}
              secondary={
                <>
                  <Chip size="small" label={c.status} sx={{ mr: 1 }} />
                  <Chip size="small" label={`schema: ${c.schema_sync_status}`} />
                </>
              }
            />
          </ListItem>
        ))}
      </List>

      <Dialog open={open} onClose={() => setOpen(false)} fullWidth maxWidth="sm">
        <DialogTitle>New database connection</DialogTitle>
        <DialogContent>
          <Stack spacing={2} mt={1}>
            <TextField
              label="Name"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
            />
            <TextField
              select
              label="Database type"
              value={form.database_type}
              onChange={(e) => setForm({ ...form, database_type: e.target.value })}
            >
              {DB_TYPES.map((t) => (
                <MenuItem key={t} value={t}>
                  {t}
                </MenuItem>
              ))}
            </TextField>
            <TextField
              label="Host"
              value={form.host}
              onChange={(e) => setForm({ ...form, host: e.target.value })}
            />
            <TextField
              label="Port"
              type="number"
              value={form.port}
              onChange={(e) => setForm({ ...form, port: Number(e.target.value) })}
            />
            <TextField
              label="Database name"
              value={form.database_name}
              onChange={(e) => setForm({ ...form, database_name: e.target.value })}
            />
            <TextField
              label="Username"
              value={form.username}
              onChange={(e) => setForm({ ...form, username: e.target.value })}
            />
            <TextField
              label="Password"
              type="password"
              value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
            />
            {createMutation.isError && (
              <Typography color="error" variant="body2">
                {extractErrorMessage(createMutation.error)}
              </Typography>
            )}
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpen(false)}>Cancel</Button>
          <Button variant="contained" onClick={() => createMutation.mutate()}>
            Create
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  )
}

function KnowledgeBasesPanel() {
  const queryClient = useQueryClient()
  const [name, setName] = useState('')

  const { data: kbs } = useQuery({
    queryKey: ['knowledge-bases'],
    queryFn: async () => (await api.get<KnowledgeBase[]>('/knowledge-bases')).data,
  })
  const { data: files } = useQuery({
    queryKey: ['files'],
    queryFn: async () => (await api.get<FileRecord[]>('/files')).data,
    refetchInterval: 4000,
  })

  const createKb = useMutation({
    mutationFn: async () => api.post('/knowledge-bases', { name }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['knowledge-bases'] })
      setName('')
    },
  })

  const uploadFile = useMutation({
    mutationFn: async ({ file, kbId }: { file: File; kbId: string }) => {
      const formData = new FormData()
      formData.append('upload', file)
      formData.append('knowledge_base_id', kbId)
      return api.post('/files/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['files'] }),
  })

  return (
    <Box mt={4}>
      <Typography variant="h6" mb={1}>
        Knowledge bases
      </Typography>
      <Stack direction="row" spacing={1} mb={2}>
        <TextField size="small" label="New KB name" value={name} onChange={(e) => setName(e.target.value)} />
        <Button variant="outlined" onClick={() => createKb.mutate()} disabled={!name}>
          Create
        </Button>
      </Stack>
      <List dense>
        {kbs?.map((kb) => (
          <ListItem
            key={kb.id}
            secondaryAction={
              <Button component="label" size="small">
                Upload file
                <input
                  hidden
                  type="file"
                  accept=".pdf,.docx,.xlsx,.csv,.txt"
                  onChange={(e) => {
                    const file = e.target.files?.[0]
                    if (file) uploadFile.mutate({ file, kbId: kb.id })
                    e.target.value = ''
                  }}
                />
              </Button>
            }
          >
            <ListItemText primary={kb.name} secondary={kb.description} />
          </ListItem>
        ))}
      </List>

      <Typography variant="subtitle1" mt={2}>
        Files
      </Typography>
      <List dense>
        {files?.map((f) => (
          <ListItem key={f.id}>
            <ListItemText
              primary={f.original_name}
              secondary={`${f.processing_status}${f.page_count ? ` · ${f.page_count} pages` : ''}${
                f.processing_error ? ` · ${f.processing_error}` : ''
              }`}
            />
          </ListItem>
        ))}
      </List>
    </Box>
  )
}

export function DashboardPage() {
  return (
    <Box maxWidth={700} mx="auto" py={4} px={2}>
      <ConnectionsPanel />
      <KnowledgeBasesPanel />
    </Box>
  )
}
