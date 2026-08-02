import { useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Box,
  Button,
  Checkbox,
  Chip,
  FormControlLabel,
  Paper,
  Stack,
  TextField,
  Typography,
} from '@mui/material'
import { api } from '../api/client'
import type { Citation, DatabaseConnection, KnowledgeBase, SqlSummary } from '../api/types'

interface DisplayMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  intent?: string
  sourcesUsed?: string[]
  sql?: SqlSummary | null
  citations?: Citation[]
}

export function ChatPage() {
  const [selectedConnections, setSelectedConnections] = useState<string[]>([])
  const [selectedKbs, setSelectedKbs] = useState<string[]>([])
  const [input, setInput] = useState('')
  const [conversationId, setConversationId] = useState<string | null>(null)
  const [messages, setMessages] = useState<DisplayMessage[]>([])
  const [sending, setSending] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  const { data: connections } = useQuery({
    queryKey: ['connections'],
    queryFn: async () => (await api.get<DatabaseConnection[]>('/database-connections')).data,
  })
  const { data: kbs } = useQuery({
    queryKey: ['knowledge-bases'],
    queryFn: async () => (await api.get<KnowledgeBase[]>('/knowledge-bases')).data,
  })

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const toggle = (list: string[], setList: (v: string[]) => void, id: string) => {
    setList(list.includes(id) ? list.filter((x) => x !== id) : [...list, id])
  }

  const sendMessage = async () => {
    if (!input.trim() || sending) return
    const question = input
    setInput('')
    setSending(true)

    const userMessage: DisplayMessage = { id: `local-${Date.now()}`, role: 'user', content: question }
    const assistantMessage: DisplayMessage = { id: `pending-${Date.now()}`, role: 'assistant', content: '' }
    setMessages((prev) => [...prev, userMessage, assistantMessage])

    try {
      const token = localStorage.getItem('access_token')
      const response = await fetch('/api/chat/stream', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: token ? `Bearer ${token}` : '',
        },
        body: JSON.stringify({
          conversation_id: conversationId,
          message: question,
          database_connection_ids: selectedConnections,
          knowledge_base_ids: selectedKbs,
        }),
      })

      if (!response.body) throw new Error('No response body')
      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let currentEvent = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() ?? ''

        for (const line of lines) {
          if (line.startsWith('event: ')) {
            currentEvent = line.slice('event: '.length).trim()
          } else if (line.startsWith('data: ')) {
            const payload = JSON.parse(line.slice('data: '.length))
            setMessages((prev) => {
              const next = [...prev]
              const last = next[next.length - 1]
              if (last.role !== 'assistant') return next

              if (currentEvent === 'intent') last.intent = payload.intent
              if (currentEvent === 'source') last.sourcesUsed = [...(last.sourcesUsed ?? []), payload.source]
              if (currentEvent === 'sql') last.sql = payload
              if (currentEvent === 'citation') last.citations = [...(last.citations ?? []), payload]
              if (currentEvent === 'token') last.content += payload.text
              if (currentEvent === 'completed') {
                last.id = payload.message_id
                if (payload.conversation_id) setConversationId(payload.conversation_id)
              }
              return next
            })
          }
        }
      }
    } finally {
      setSending(false)
    }
  }

  return (
    <Box display="flex" height="100vh">
      <Box width={280} borderRight={1} borderColor="divider" p={2} overflow="auto">
        <Typography variant="subtitle2" gutterBottom>
          Database connections
        </Typography>
        {connections?.map((c) => (
          <FormControlLabel
            key={c.id}
            control={
              <Checkbox
                checked={selectedConnections.includes(c.id)}
                onChange={() => toggle(selectedConnections, setSelectedConnections, c.id)}
              />
            }
            label={c.name}
          />
        ))}

        <Typography variant="subtitle2" gutterBottom mt={2}>
          Knowledge bases
        </Typography>
        {kbs?.map((kb) => (
          <FormControlLabel
            key={kb.id}
            control={
              <Checkbox
                checked={selectedKbs.includes(kb.id)}
                onChange={() => toggle(selectedKbs, setSelectedKbs, kb.id)}
              />
            }
            label={kb.name}
          />
        ))}
      </Box>

      <Box flex={1} display="flex" flexDirection="column">
        <Box flex={1} overflow="auto" p={2}>
          {messages.map((m) => (
            <Paper
              key={m.id}
              variant="outlined"
              sx={{
                p: 2,
                mb: 2,
                ml: m.role === 'user' ? 8 : 0,
                mr: m.role === 'assistant' ? 8 : 0,
                bgcolor: m.role === 'user' ? 'primary.50' : 'background.paper',
              }}
            >
              <Typography variant="caption" color="text.secondary">
                {m.role}
                {m.intent && ` · intent: ${m.intent}`}
              </Typography>
              <Typography whiteSpace="pre-wrap">{m.content}</Typography>

              {m.sql && (
                <Box mt={1} p={1} bgcolor="grey.100" borderRadius={1}>
                  <Typography variant="caption" fontFamily="monospace" whiteSpace="pre-wrap">
                    {m.sql.query}
                  </Typography>
                  <Typography variant="caption" display="block" color="text.secondary">
                    {m.sql.row_count} row(s)
                  </Typography>
                </Box>
              )}

              {m.citations && m.citations.length > 0 && (
                <Stack direction="row" spacing={1} mt={1} flexWrap="wrap">
                  {m.citations.map((c, i) => (
                    <Chip
                      key={i}
                      size="small"
                      label={
                        c.type === 'document'
                          ? `${c.file_name}${c.page ? ` p.${c.page}` : ''}`
                          : `DB: ${c.tables?.join(', ')}`
                      }
                    />
                  ))}
                </Stack>
              )}
            </Paper>
          ))}
          <div ref={bottomRef} />
        </Box>

        <Box p={2} borderTop={1} borderColor="divider">
          <Stack direction="row" spacing={1}>
            <TextField
              fullWidth
              placeholder="Ask a question about your database or documents..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  sendMessage()
                }
              }}
            />
            <Button variant="contained" onClick={sendMessage} disabled={sending}>
              Send
            </Button>
          </Stack>
        </Box>
      </Box>
    </Box>
  )
}
