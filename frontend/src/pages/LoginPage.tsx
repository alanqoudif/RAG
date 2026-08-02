import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { z } from 'zod'
import { useNavigate } from 'react-router-dom'
import { useState } from 'react'
import { Box, Button, Card, CardContent, Stack, TextField, Typography, Alert } from '@mui/material'
import { useAuth } from '../context/AuthContext'
import { extractErrorMessage } from '../api/client'

const schema = z.object({
  tenantCode: z.string().min(1, 'Required'),
  email: z.string().email('Invalid email'),
  password: z.string().min(1, 'Required'),
})

type FormValues = z.infer<typeof schema>

export function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [error, setError] = useState<string | null>(null)
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { tenantCode: 'acme', email: 'admin@acme.io', password: 'DemoAdmin123!' },
  })

  const onSubmit = async (values: FormValues) => {
    setError(null)
    try {
      await login(values.tenantCode, values.email, values.password)
      navigate('/chat')
    } catch (err) {
      setError(extractErrorMessage(err))
    }
  }

  return (
    <Box display="flex" alignItems="center" justifyContent="center" minHeight="100vh" bgcolor="grey.100">
      <Card sx={{ width: 380 }}>
        <CardContent>
          <Typography variant="h5" gutterBottom>
            Text-to-SQL &amp; Document Chat
          </Typography>
          <Typography variant="body2" color="text.secondary" gutterBottom>
            Demo credentials are pre-filled (tenant "acme").
          </Typography>
          <form onSubmit={handleSubmit(onSubmit)}>
            <Stack spacing={2} mt={2}>
              {error && <Alert severity="error">{error}</Alert>}
              <TextField
                label="Tenant code"
                {...register('tenantCode')}
                error={!!errors.tenantCode}
                helperText={errors.tenantCode?.message}
              />
              <TextField
                label="Email"
                {...register('email')}
                error={!!errors.email}
                helperText={errors.email?.message}
              />
              <TextField
                label="Password"
                type="password"
                {...register('password')}
                error={!!errors.password}
                helperText={errors.password?.message}
              />
              <Button type="submit" variant="contained" disabled={isSubmitting}>
                Sign in
              </Button>
            </Stack>
          </form>
        </CardContent>
      </Card>
    </Box>
  )
}
