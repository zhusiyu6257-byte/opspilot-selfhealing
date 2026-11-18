<script setup>
import { computed, nextTick, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Monitor } from '@element-plus/icons-vue'
import { createAsset } from '../api'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue', 'created'])

const visible = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value),
})

const INITIAL_FORM = {
  name: '',
  ip_address: '',
  os_type: 'Linux',
  ssh_port: 22,
  ssh_user: 'root',
}

const formRef = ref()
const form = reactive({ ...INITIAL_FORM })
const submitting = ref(false)
const formError = ref('')

const validateIp = (rule, value, callback) => {
  const ipv4 = /^(25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)){3}$/
  if (!value) return callback(new Error('请输入 IP 地址'))
  if (!ipv4.test(value) && !/^[\da-fA-F:.]+$/.test(value)) {
    return callback(new Error('请输入合法的 IPv4 或 IPv6 地址'))
  }
  return callback()
}

const rules = {
  name: [
    { required: true, message: '请输入主机名称', trigger: 'blur' },
    {
      pattern: /^[A-Za-z0-9._-]{2,64}$/,
      message: '仅支持字母、数字、点、下划线、连字符（2-64 位）',
      trigger: 'blur',
    },
  ],
  ip_address: [{ validator: validateIp, trigger: 'blur' }],
  os_type: [{ required: true, message: '请选择操作系统', trigger: 'change' }],
  ssh_port: [
    {
      validator: (rule, value, callback) => {
        if (!Number.isInteger(value) || value < 1 || value > 65535) {
          return callback(new Error('端口范围 1-65535'))
        }
        return callback()
      },
      trigger: 'change',
    },
  ],
  ssh_user: [{ required: true, message: '请输入 SSH 用户名', trigger: 'blur' }],
}

watch(visible, (open) => {
  if (open) {
    formError.value = ''
    nextTick(() => formRef.value?.clearValidate())
  }
})

const resetForm = () => {
  Object.assign(form, INITIAL_FORM)
  nextTick(() => formRef.value?.clearValidate())
}

const handleSubmit = async () => {
  formError.value = ''
  try {
    await formRef.value.validate()
  } catch {
    return
  }

  submitting.value = true
  try {
    await createAsset({
      name: form.name.trim(),
      ip_address: form.ip_address.trim(),
      os_type: form.os_type,
      ssh_port: Number(form.ssh_port),
      ssh_user: form.ssh_user.trim(),
    })
    ElMessage.success(`主机 ${form.name} 已纳入资产清单`)
    emit('created')
    visible.value = false
    resetForm()
  } catch (err) {
    formError.value = err.message
    ElMessage.error(`录入失败：${err.message}`)
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <el-dialog
    v-model="visible"
    width="540px"
    align-center
    :close-on-click-modal="false"
    destroy-on-close
    class="op-dialog"
  >
    <template #header>
      <div class="dlg-head">
        <div class="dlg-head__icon"><el-icon :size="18"><Monitor /></el-icon></div>
        <div>
          <div class="dlg-head__title">录入新主机资产</div>
          <div class="dlg-head__sub op-mono">POST /api/v1/assets</div>
        </div>
      </div>
    </template>

    <el-form ref="formRef" :model="form" :rules="rules" label-position="top">
      <div class="dlg-grid">
        <el-form-item label="主机名称" prop="name">
          <el-input v-model="form.name" placeholder="node-prod-02" clearable />
        </el-form-item>
        <el-form-item label="IP 地址" prop="ip_address">
          <el-input v-model="form.ip_address" placeholder="192.168.1.101" clearable />
        </el-form-item>
        <el-form-item label="操作系统" prop="os_type">
          <el-select v-model="form.os_type" style="width: 100%">
            <el-option label="Linux" value="Linux" />
            <el-option label="Windows" value="Windows" />
            <el-option label="Darwin / macOS" value="Darwin" />
            <el-option label="其他" value="Other" />
          </el-select>
        </el-form-item>
        <el-form-item label="SSH 端口" prop="ssh_port">
          <el-input-number
            v-model="form.ssh_port"
            :min="1"
            :max="65535"
            controls-position="right"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="SSH 用户" prop="ssh_user">
          <el-input v-model="form.ssh_user" placeholder="root" clearable />
        </el-form-item>
        <el-form-item label="初始状态">
          <el-input model-value="待探测 (unknown)" disabled />
        </el-form-item>
      </div>

      <el-alert type="info" :closable="false" show-icon class="dlg-note">
        <template #title>SSH 密码不入库</template>
        凭据只在下发剧本时按需填写，随单次请求发送；此处仅登记连接信息。
      </el-alert>

      <el-alert
        v-if="formError"
        type="error"
        :closable="false"
        show-icon
        class="dlg-error"
        :title="formError"
      />
    </el-form>

    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="handleSubmit">
        {{ submitting ? '正在录入…' : '确认录入' }}
      </el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.dlg-head {
  display: flex;
  align-items: center;
  gap: 12px;
}

.dlg-head__icon {
  display: grid;
  place-items: center;
  width: 36px;
  height: 36px;
  border-radius: 10px;
  background: rgba(34, 197, 94, 0.1);
  border: 1px solid rgba(34, 197, 94, 0.22);
  color: var(--op-accent-bright);
}

.dlg-head__title {
  font-size: 15px;
  font-weight: 650;
}

.dlg-head__sub {
  margin-top: 4px;
  font-size: 10px;
  color: var(--op-faint);
}

.dlg-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  column-gap: 16px;
}

.dlg-note {
  margin-top: 4px;
  background: rgba(56, 189, 248, 0.06);
  border: 1px solid rgba(56, 189, 248, 0.18);
}

.dlg-error {
  margin-top: 12px;
}

@media (max-width: 560px) {
  .dlg-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
