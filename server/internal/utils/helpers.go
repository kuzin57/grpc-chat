package utils

func MapSlice[T any, R any](slice []T, fn func(T) R) []R {
	result := make([]R, len(slice))
	for i, v := range slice {
		result[i] = fn(v)
	}
	return result
}

func MapSliceIf[T any, R any](slice []T, fn func(T) (R, bool)) []R {
	result := make([]R, 0)
	for _, v := range slice {
		if r, ok := fn(v); ok {
			result = append(result, r)
		}
	}
	return result
}

func FilterSlice[T any](slice []T, fn func(T) bool) []T {
	result := make([]T, 0)
	for _, v := range slice {
		if fn(v) {
			result = append(result, v)
		}
	}
	return result
}
